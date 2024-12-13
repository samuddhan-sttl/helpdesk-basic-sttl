odoo.define('website_helpdesk.helpdesk', function (require) {
    "use strict";

    var _t = require('web.core')._t;
    var ajax = require('web.ajax');
    var publicWidget = require('web.public.widget');
    var session = require("web.session");
    

    publicWidget.registry.LogData = publicWidget.Widget.extend({
        selector: '#helpdesk_form',
        events: Object.assign({}, publicWidget.Widget.prototype.events, {
            'change .uploaded_file': 'FileUpload',
        }),

        FileUpload: function(event) {
            var files = event.target.files;
            var file_data = {};
            $('.file_data').remove();
            $('.pip').remove();
            for (var i = 0; i < files.length; i++) {
                var file = files[i];
                var is_allowed_type = /^(image\/.*|application\/pdf|application\/vnd\.ms-excel|application\/vnd\.openxmlformats-officedocument\.spreadsheetml\.sheet|application\/msword|application\/vnd\.openxmlformats-officedocument\.wordprocessingml\.document|application\/vnd\.ms-powerpoint|application\/vnd\.openxmlformats-officedocument\.presentationml\.presentation|text\/csv|text\/plain)$/.test(file.type);
                file_data.name = file.name;
                file_data.type = file.type;
                if (!is_allowed_type) {
                    this.DiplayAlert(_t("Invalid file type. Please select Image, PDF, Excel, Word, PowerPoint, CSV, or TXT file"));
                    this.ResetFile();
                    return;
                }
                if (file.size / 1024 / 1024 > 25) {
                    this.DiplayAlert(_t("File is too big. File size cannot exceed 25MB"));
                    this.ResetFile();
                    return;
                }
                $('.alert-warning').remove();
                var BinaryReader = new FileReader();
                BinaryReader.readAsDataURL(file);
                BinaryReader.onloadend = function (upload) {
                    var buffer = upload.target.result;
                    buffer = buffer.split(',')[1];

                    var file_name = 'file_data_' + _.uniqueId([2]);
                    $('#file_upload_data').append($('<input class="form-group file_data" name=' + file_name + ' type="hidden" value="' + buffer + '"/>'));

                    var fileExtension = file.name.split('.').pop().toLowerCase();
                    var fileIcon = '';
                    if (fileExtension === 'pdf') {
                        fileIcon = '<i class="fa fa-file-pdf-o" aria-hidden="true"></i>';
                    } else if (fileExtension === 'xlsx' || fileExtension === 'xls') {
                        fileIcon = '<i class="fa fa-file-excel-o" aria-hidden="true"></i>';
                    } else if (fileExtension === 'doc' || fileExtension === 'docx') {
                        fileIcon = '<i class="fa fa-file-word-o" aria-hidden="true"></i>';
                    } else if (fileExtension === 'ppt' || fileExtension === 'pptx') {
                        fileIcon = '<i class="fa fa-file-powerpoint-o" aria-hidden="true"></i>';
                    } else if (fileExtension === 'csv') {
                        fileIcon = '<i class="fa fa-file-code-o" aria-hidden="true"></i>';
                    } else if (fileExtension === 'txt') {
                        fileIcon = '<i class="fa fa-file-text-o" aria-hidden="true"></i>';
                    } else {
                        fileIcon = '<img class="imageThumb" src="' + upload.target.result + '" title="' + file.name + '"/>';
                    }
                    
                    $("<span class=\"pip\" name=\"" + file_name + "\" >" + fileIcon + "<br/><span class=\"remove\">Remove file</span></span>").insertAfter("#upload");
                    $(".remove").click(function () {
                        $(this).parent(".pip").remove();
                        var file_name = $('[name=' + $(this).parent(".pip").attr("name") + ']');
                        $('#upload').val("");
                        $(file_name).remove();
                    });
                };
            }
        },
        DiplayAlert: function (message) {
            $('.alert-warning').remove();
            $('<div class="alert alert-warning" role="alert">' + message + '</div>'
            ).insertBefore($('form'));
        },
        ResetFile: function () {
            $('#upload').val('');
        }
    });
    return publicWidget
});
