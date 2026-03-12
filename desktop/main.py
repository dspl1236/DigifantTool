"""
DigiTool Desktop — Digifant 1 G60/G40 ECU Editor
Wraps the HTML tool in a native desktop window using pywebview.
"""
import sys
import os
import webview
import tempfile
import shutil

APP_TITLE = "DigiTool — Digifant 1 G60/G40 ECU Editor"
APP_VERSION = "0.1.0"

def get_html_path():
    """Find the HTML file whether running as script or frozen exe."""
    if getattr(sys, 'frozen', False):
        # PyInstaller bundle — look next to the exe
        base = sys._MEIPASS
    else:
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    html = os.path.join(base, 'app', 'DigiTool.html')
    if os.path.exists(html):
        return html
    # Fallback: same dir as script
    html2 = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'DigiTool.html')
    if os.path.exists(html2):
        return html2
    raise FileNotFoundError(f"DigiTool.html not found. Looked in:\n  {html}\n  {html2}")


class Api:
    """Python ↔ JS bridge for native file dialogs and file I/O."""

    def open_file_dialog(self):
        """Show native open dialog, return list of {name, path} dicts."""
        result = window.create_file_dialog(
            webview.OPEN_DIALOG,
            allow_multiple=True,
            file_types=('ROM Files (*.bin;*.BIN)', 'All files (*.*)')
        )
        if not result:
            return []
        files = []
        for path in result:
            files.append({'name': os.path.basename(path), 'path': path})
        return files

    def read_file(self, path):
        """Read a file as a list of byte integers."""
        try:
            with open(path, 'rb') as f:
                data = f.read()
            return list(data)
        except Exception as e:
            return {'error': str(e)}

    def save_file_dialog(self, suggested_name='modified.BIN'):
        """Show native save dialog, return chosen path or None."""
        result = window.create_file_dialog(
            webview.SAVE_DIALOG,
            save_filename=suggested_name,
            file_types=('ROM Files (*.bin;*.BIN)', 'All files (*.*)')
        )
        return result

    def write_file(self, path, bytes_list):
        """Write a list of byte integers to a file."""
        try:
            data = bytes(bytes_list)
            with open(path, 'wb') as f:
                f.write(data)
            return {'ok': True, 'size': len(data)}
        except Exception as e:
            return {'error': str(e)}

    def get_version(self):
        return APP_VERSION


def main():
    api = Api()
    html_path = get_html_path()
    html_url = f'file:///{html_path.replace(os.sep, "/")}'

    global window
    window = webview.create_window(
        title=APP_TITLE,
        url=html_url,
        js_api=api,
        width=1280,
        height=820,
        min_size=(900, 600),
        confirm_close=False,
    )

    # Inject native file dialog bridge after page loads
    def on_loaded():
        window.evaluate_js("""
        // Override browser file input with native dialog
        if (typeof window.pywebview !== 'undefined') {
            window._nativeMode = true;

            // Patch the drop zone click to use native dialog
            const origDropZoneClick = document.getElementById('dropZone').onclick;
            document.getElementById('dropZone').onclick = async function() {
                const files = await pywebview.api.open_file_dialog();
                if (!files || files.length === 0) return;
                for (const f of files) {
                    const bytes = await pywebview.api.read_file(f.path);
                    if (bytes.error) { alert('Error reading: ' + f.path + '\\n' + bytes.error); continue; }
                    const arr = new Uint8Array(bytes);
                    // Simulate what loadFile does
                    if (arr.length !== 32768) {
                        alert(f.name + ': Expected 32768 bytes, got ' + arr.length);
                        continue;
                    }
                    const existing = roms.findIndex(r => r.name === f.name);
                    if (existing >= 0) roms[existing].data = arr;
                    else roms.push({name: f.name, data: arr});
                    renderFileList();
                    if (activeFileIdx < 0) selectFile(0);
                    else if (roms.length >= 2 && refFileIdx < 0) selectRefFile(roms.length-1);
                }
            };

            // Patch export to use native save dialog
            window._origExportROM = window.exportROM;
            window.exportROM = async function(which) {
                const idx = (which === 'ref') ? refFileIdx : activeFileIdx;
                if (idx < 0 || !roms[idx]) { alert('No ROM loaded'); return; }
                const savePath = await pywebview.api.save_file_dialog(roms[idx].name);
                if (!savePath) return;
                const result = await pywebview.api.write_file(savePath, Array.from(roms[idx].data));
                if (result.error) alert('Save failed: ' + result.error);
                else alert('Saved ' + result.size + ' bytes to:\\n' + savePath);
            };

            // Show native mode indicator
            const hdr = document.querySelector('.header-status');
            if (hdr) {
                const badge = document.createElement('span');
                badge.style.cssText = 'background:rgba(75,232,122,0.15);color:var(--accent3);padding:2px 8px;border-radius:2px;font-family:var(--mono);font-size:10px;letter-spacing:1px';
                badge.textContent = 'NATIVE';
                hdr.prepend(badge);
            }
        }
        """)

    window.events.loaded += on_loaded
    webview.start(debug=False)


if __name__ == '__main__':
    main()
