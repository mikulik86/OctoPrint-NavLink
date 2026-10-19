# coding=utf-8
"""Nav Link – adds a configurable link button to OctoPrint's top navigation bar."""

import os
import re
import time

import flask

import octoprint.plugin
from octoprint.access.permissions import Permissions

# Allowed icon formats: extension -> MIME type
ICON_TYPES = {
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "gif": "image/gif",
    "webp": "image/webp",
    "svg": "image/svg+xml",
    "ico": "image/x-icon",
}
ICON_FILE_PATTERN = re.compile(r"^icon\.(png|jpe?g|gif|webp|svg|ico)$")
MAX_ICON_BYTES = 1024 * 1024  # 1 MB


def _looks_like(ext, head):
    """Cheap content check so a renamed non-image file is rejected."""
    if ext == "png":
        return head.startswith(b"\x89PNG\r\n\x1a\n")
    if ext in ("jpg", "jpeg"):
        return head.startswith(b"\xff\xd8\xff")
    if ext == "gif":
        return head.startswith(b"GIF87a") or head.startswith(b"GIF89a")
    if ext == "webp":
        return head[:4] == b"RIFF" and head[8:12] == b"WEBP"
    if ext == "ico":
        return head.startswith(b"\x00\x00\x01\x00")
    if ext == "svg":
        return b"<svg" in head.lower()
    return False


class NavLinkPlugin(
    octoprint.plugin.SettingsPlugin,
    octoprint.plugin.TemplatePlugin,
    octoprint.plugin.AssetPlugin,
    octoprint.plugin.BlueprintPlugin,
):
    # ~~ SettingsPlugin

    def get_settings_defaults(self):
        return {
            "url": "",
            "label": "",
            "icon_type": "fontawesome",  # "fontawesome" or "image"
            "icon": "fas fa-external-link-alt",
            "icon_file": "",  # managed by the upload endpoint only
            "icon_version": 0,  # cache buster for the uploaded image
            "tooltip": "",
            "new_tab": True,
        }

    def get_settings_version(self):
        return 2

    def on_settings_migrate(self, target, current):
        # 1.1.0 had a "right_spacing" setting that was removed again in 1.1.1
        if current is None or current < 2:
            self._settings.remove(["right_spacing"])

    def on_settings_save(self, data):
        # The uploaded file is managed by the /icon endpoints; never let a
        # settings save point it somewhere else.
        data.pop("icon_file", None)
        data.pop("icon_version", None)
        return octoprint.plugin.SettingsPlugin.on_settings_save(self, data)

    # ~~ TemplatePlugin

    def get_template_configs(self):
        return [
            {"type": "navbar", "custom_bindings": True},
            {"type": "settings", "custom_bindings": True},
        ]

    def is_template_autoescaped(self):
        # Our templates contain no Jinja variables, so autoescaping is safe
        # (and required from OctoPrint 1.13 on).
        return True

    # ~~ AssetPlugin

    def get_assets(self):
        return {"js": ["js/navlink.js"], "css": ["css/navlink.css"]}

    # ~~ BlueprintPlugin

    def is_blueprint_protected(self):
        return True  # a logged-in user is needed, the navbar is only shown to them anyway

    def is_blueprint_csrf_protected(self):
        return True

    def _icon_path(self):
        name = self._settings.get(["icon_file"]) or ""
        if not ICON_FILE_PATTERN.match(name):
            return None, None
        path = os.path.join(self.get_plugin_data_folder(), name)
        if not os.path.isfile(path):
            return None, None
        return path, name.rsplit(".", 1)[1]

    def _remove_icon_files(self):
        folder = self.get_plugin_data_folder()
        for name in os.listdir(folder):
            if ICON_FILE_PATTERN.match(name):
                try:
                    os.remove(os.path.join(folder, name))
                except OSError:
                    self._logger.exception("Could not remove old icon %s", name)

    @octoprint.plugin.BlueprintPlugin.route("/icon", methods=["GET"])
    def get_icon(self):
        path, ext = self._icon_path()
        if path is None:
            flask.abort(404)

        with open(path, "rb") as f:
            data = f.read()

        response = flask.make_response(data)
        response.headers["Content-Type"] = ICON_TYPES[ext]
        response.headers["Cache-Control"] = "private, max-age=604800"
        # An SVG opened directly must not be able to run scripts in OctoPrint's origin
        response.headers["Content-Security-Policy"] = (
            "default-src 'none'; img-src data:; style-src 'unsafe-inline'; sandbox"
        )
        return response

    @octoprint.plugin.BlueprintPlugin.route("/icon", methods=["POST"])
    @Permissions.SETTINGS.require(403)
    def upload_icon(self):
        # OctoPrint streams uploads to a temp file and hands us its path and name
        path_key = "file." + self._settings.global_get(["server", "uploads", "pathSuffix"])
        name_key = "file." + self._settings.global_get(["server", "uploads", "nameSuffix"])
        upload_path = flask.request.values.get(path_key)
        upload_name = flask.request.values.get(name_key) or ""
        if not upload_path or not os.path.isfile(upload_path):
            return flask.make_response(flask.jsonify(error="No file was uploaded."), 400)

        ext = upload_name.rsplit(".", 1)[-1].lower() if "." in upload_name else ""
        if ext not in ICON_TYPES:
            return flask.make_response(
                flask.jsonify(error="Unsupported file type. Use PNG, JPG, GIF, WebP, SVG or ICO."),
                400,
            )

        if os.path.getsize(upload_path) > MAX_ICON_BYTES:
            return flask.make_response(flask.jsonify(error="The image is larger than 1 MB."), 400)

        with open(upload_path, "rb") as f:
            data = f.read()
        if not _looks_like(ext, data[:2048]):
            return flask.make_response(
                flask.jsonify(error="That file doesn't look like a valid ." + ext + " image."), 400
            )

        if ext == "jpeg":
            ext = "jpg"
        filename = "icon." + ext
        self._remove_icon_files()
        with open(os.path.join(self.get_plugin_data_folder(), filename), "wb") as f:
            f.write(data)

        version = int(time.time() * 1000)
        self._settings.set(["icon_file"], filename)
        self._settings.set(["icon_version"], version)
        self._settings.save()
        self._logger.info("New navbar icon uploaded (%s, %d bytes)", filename, len(data))

        return flask.jsonify(icon_file=filename, icon_version=version)

    @octoprint.plugin.BlueprintPlugin.route("/icon", methods=["DELETE"])
    @Permissions.SETTINGS.require(403)
    def delete_icon(self):
        self._remove_icon_files()
        version = int(time.time() * 1000)
        self._settings.set(["icon_file"], "")
        self._settings.set(["icon_version"], version)
        self._settings.save()
        return flask.jsonify(icon_file="", icon_version=version)

    # ~~ octoprint.server.http.bodysize hook

    def increase_upload_bodysize(self, current_max_body_sizes, *args, **kwargs):
        # default request limit is too small for an image; the view enforces 1 MB itself
        return [("POST", r"/icon", 2 * MAX_ICON_BYTES)]

    # ~~ Software Update hook

    def get_update_information(self):
        return {
            "navlink": {
                "displayName": "Nav Link",
                "displayVersion": self._plugin_version,
                "type": "github_release",
                "user": "mikulik86",
                "repo": "OctoPrint-NavLink",
                "current": self._plugin_version,
                "pip": "https://github.com/mikulik86/OctoPrint-NavLink/archive/{target_version}.zip",
            }
        }


__plugin_name__ = "Nav Link"
__plugin_description__ = "Adds a link button with a configurable URL and icon to the top navigation bar."
__plugin_version__ = "1.2.0"
__plugin_author__ = "mikulik86"
__plugin_url__ = "https://github.com/mikulik86/OctoPrint-NavLink"
__plugin_license__ = "MIT"
__plugin_pythoncompat__ = ">=3.7,<4"
__plugin_implementation__ = NavLinkPlugin()
__plugin_hooks__ = {
    "octoprint.server.http.bodysize": __plugin_implementation__.increase_upload_bodysize,
    "octoprint.plugin.softwareupdate.check_config": __plugin_implementation__.get_update_information,
}
