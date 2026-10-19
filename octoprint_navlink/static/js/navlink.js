/*
 * Nav Link – view model for the navbar button and the settings page.
 * The button follows the settings observables, so edits preview live and
 * a Save applies them without a page reload.
 */
$(function () {
    var DEFAULT_ICON = "fas fa-external-link-alt";

    function NavLinkViewModel(parameters) {
        var self = this;
        self.settingsViewModel = parameters[0];

        // Settings-page state
        self.uploading = ko.observable(false);
        self.uploadError = ko.observable("");
        self.imageFailed = ko.observable(false);

        self.onBeforeBinding = function () {
            var cfg = (self.cfg = self.settingsViewModel.settings.plugins.navlink);
            var trim = function (v) {
                return $.trim(v || "");
            };

            self.hasUrl = ko.pureComputed(function () {
                return trim(cfg.url()) !== "";
            });
            self.href = ko.pureComputed(function () {
                return self.hasUrl() ? trim(cfg.url()) : "#";
            });
            self.target = ko.pureComputed(function () {
                return self.hasUrl() && cfg.new_tab() ? "_blank" : null;
            });
            self.title = ko.pureComputed(function () {
                if (!self.hasUrl()) {
                    return "Nav Link: set a URL in Settings → Nav Link";
                }
                return trim(cfg.tooltip()) || trim(cfg.url());
            });
            self.labelText = ko.pureComputed(function () {
                return trim(cfg.label());
            });

            // Uploaded image
            self.hasImageFile = ko.pureComputed(function () {
                return trim(cfg.icon_file()) !== "";
            });
            self.imageUrl = ko.pureComputed(function () {
                return (
                    OctoPrint.getBaseUrl() +
                    "plugin/navlink/icon?v=" +
                    encodeURIComponent(cfg.icon_version() || 0)
                );
            });
            self.imageUrl.subscribe(function () {
                self.imageFailed(false);
            });
            self.showImage = ko.pureComputed(function () {
                return (
                    cfg.icon_type() === "image" && self.hasImageFile() && !self.imageFailed()
                );
            });

            // Font Awesome icon (also the fallback when no image is available)
            self.faIcon = ko.pureComputed(function () {
                if (self.showImage()) {
                    return "";
                }
                var icon = trim(cfg.icon());
                if (cfg.icon_type() === "image" || (icon === "" && self.labelText() === "")) {
                    // never render an invisible button
                    return icon || DEFAULT_ICON;
                }
                return icon;
            });
            self.hasIcon = ko.pureComputed(function () {
                return self.showImage() || self.faIcon() !== "";
            });
        };

        // No URL yet: clicking the button opens our settings page instead.
        self.onClick = function () {
            if (self.hasUrl()) {
                return true; // let the browser follow the link
            }
            self.settingsViewModel.show("#settings_plugin_navlink");
            return false;
        };

        self.onImageError = function () {
            self.imageFailed(true);
        };

        // ~~ Settings page: upload / remove

        self.chooseFile = function () {
            $("#navlink-icon-file").trigger("click");
        };

        self.fileSelected = function (data, event) {
            var input = event.target;
            if (!input.files || !input.files.length) {
                return;
            }
            var file = input.files[0];
            input.value = ""; // allow picking the same file again

            if (file.size > 1024 * 1024) {
                self.uploadError("The image is larger than 1 MB.");
                return;
            }

            self.uploading(true);
            self.uploadError("");
            OctoPrint.upload("plugin/navlink/icon", file, file.name)
                .done(function (result) {
                    var json = result[0];
                    self.cfg.icon_file(json.icon_file);
                    self.cfg.icon_version(json.icon_version);
                    self.cfg.icon_type("image");
                })
                .fail(function (result) {
                    var request = result[0];
                    var message = "Upload failed.";
                    if (request && request.status === 413) {
                        message = "The image is larger than 1 MB.";
                    } else if (request && request.status === 403) {
                        message = "You don't have permission to change settings.";
                    } else {
                        try {
                            message = JSON.parse(request.response).error || message;
                        } catch (e) {
                            // keep the generic message
                        }
                    }
                    self.uploadError(message);
                })
                .always(function () {
                    self.uploading(false);
                });
        };

        self.removeImage = function () {
            self.uploadError("");
            OctoPrint.delete("plugin/navlink/icon")
                .done(function (json) {
                    self.cfg.icon_file(json.icon_file);
                    self.cfg.icon_version(json.icon_version);
                })
                .fail(function () {
                    self.uploadError("Could not remove the image.");
                });
        };
    }

    OCTOPRINT_VIEWMODELS.push({
        construct: NavLinkViewModel,
        dependencies: ["settingsViewModel"],
        elements: ["#navbar_plugin_navlink", "#settings_plugin_navlink"]
    });
});
