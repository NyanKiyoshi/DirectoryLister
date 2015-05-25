var app = angular.module('Dialog', ['ngDialog']);

app.controller('MainCtrl', function ($scope, $rootScope, $http, ngDialog) {
    $rootScope.theme = 'ngdialog-theme-default';
    $scope.openDefault = function (path, file_name) {
        ngDialog.open({
            template: 'getHashes',
            controller: ['$scope', '$timeout', 'ngDialog', function ($scope, $timeout) {
                $scope.file_name = file_name;
                var send_msg = function(msg, sha1_msg) {
                    document.getElementById('md5').value  = msg;
                    document.getElementById('sha1').value = sha1_msg || msg;
                };

                $http(
                    {
                        method: 'GET',
                        url: './' + path + '?hashes',
                        isArray: true,
                        jsonCallback: 'response',
                        handleError: false
                    }
                ).success(
                    function (data, status, headers) {
                        if (headers('content-type') != 'application/json') {
                            send_msg('Error: invalid response from remote server.');
                            return;
                        }
                        if (status == 200) {
                            send_msg(data['md5'], data['sha1']);
                        } else { send_msg('Internal error.'); }
                    }
                ).error(function (data, status) {
                        switch (status) {
                            case 403:
                                send_msg('Error: ' + data['message']);
                                break;
                            case 404:
                                send_msg('Error: file not found.');
                                break;
                            default:
                                send_msg('Internal error.');
                                break;
                        }
                    }
                )
            }],
            className: 'ngdialog-theme-default',
            showClose: true,
            closeByEscape: true,
            closeByDocument: true
        });
    };
});

app.directive('selectOnClick', function () {
    return {
        restrict: 'A',
        link: function (scope, element, attrs) {
            element.on('click', function () {
                this.select();
            });
        }
    };
});
