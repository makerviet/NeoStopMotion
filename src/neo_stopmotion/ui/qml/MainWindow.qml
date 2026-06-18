import QtQuick
import QtQuick.Controls
import QtQuick.Window
import "singletons" as N
import "pages" as Pages

ApplicationWindow {
    id: root
    width: 1280
    height: 800
    visible: true
    // Maximized: trên một số nền (vd NEO One/Armbian + xfwm) cửa sổ Windowed không
    // áp được width/height và bị thu về 1x1. Maximized để WM tự co theo màn hình,
    // hợp kiosk maker-station mà vẫn còn nút đóng (khác FullScreen).
    visibility: Window.Maximized
    title: "NeoStopMotion — Trạm 6"
    color: N.NeoConstants.background

    StackView {
        id: stack
        anchors.fill: parent
        initialItem: splashComponent
        focus: true

        Keys.onPressed: function(event) {
            if (event.key === Qt.Key_Space) {
                appController.handle_uart_command("SHOOT")
                event.accepted = true
            } else if (event.key === Qt.Key_Z) {
                appController.handle_uart_command("UNDO")
                event.accepted = true
            } else if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter) {
                appController.handle_uart_command("EXPORT")
                event.accepted = true
            }
        }
    }

    Component {
        id: splashComponent
        Pages.SplashScreen {
            onFinished: stack.replace(capturePageComponent)
        }
    }

    Component {
        id: capturePageComponent
        Pages.CapturePage { }
    }

    Component {
        id: exportingPageComponent
        Pages.ExportingPage { }
    }

    Component {
        id: successPageComponent
        Pages.SuccessPage { }
    }

    Connections {
        target: appController
        function onFrameCountChanged(n) {
            N.AppState.frameCount = n
        }
    }

    Connections {
        target: signalBusBridge
        function onExportStarted() {
            stack.replace(exportingPageComponent)
        }
        function onExportProgress(p) {
            if (stack.currentItem && stack.currentItem.progress !== undefined) {
                stack.currentItem.progress = p
                if (p < 0.5) {
                    stack.currentItem.statusText = "Đang ghép phim MP4..."
                } else if (p < 0.95) {
                    stack.currentItem.statusText = "Đang tạo GIF..."
                } else {
                    stack.currentItem.statusText = "Sắp xong..."
                }
            }
        }
        function onExportCompleted(mp4Path, gifPath, shareUrl, qrPath) {
            stack.replace(successPageComponent, {
                mp4Path: mp4Path,
                gifPath: gifPath,
                shareUrl: shareUrl,
                qrPath: qrPath,
            })
        }
        function onExportFailed(msg) {
            console.log("Export failed:", msg)
            stack.replace(capturePageComponent)
        }
        function onSessionReset() {
            stack.replace(capturePageComponent)
        }
        function onStatusMessage(level, message) {
            console.log("STATUS [" + level + "] " + message)
        }
    }
}
