import os
import json
import tkinter as tk
from tkinter import filedialog, Canvas, Frame, Scrollbar
from PIL import Image, ImageTk, ImageDraw, ImageFont

CONFIG_FILE = 'config.json'
WIITDB_FILE = 'wiitdb_parsed.json'
ASSET_FOLDER = 'assets/discs'
SUPPORTED_EXTENSIONS = ['.iso', '.gcm', '.nkit.iso']

WIITDB = {}
if os.path.exists(WIITDB_FILE):
    with open(WIITDB_FILE, 'r', encoding='utf-8') as f:
        WIITDB = json.load(f)

def clean_filename(name):
    return ''.join(c for c in name if c.isalnum()).lower()

def strip_region_tags(title):
    import re
    return re.sub(r'\((USA|Europe|Japan)\)', '', title, flags=re.IGNORECASE).strip()

def extract_metadata(file_path):
    filename = os.path.splitext(os.path.basename(file_path))[0]
    display_title = strip_region_tags(filename)
    clean_name = clean_filename(filename)
    region = 'Unknown'
    if '(USA)' in filename.upper():
        region = 'NTSC-U'
    elif '(EUROPE)' in filename.upper():
        region = 'PAL'
    elif '(JAPAN)' in filename.upper():
        region = 'NTSC-J'

    best_match, best_score = None, 0
    for key, data in WIITDB.items():
        key_clean = clean_filename(key)
        if clean_name in key_clean or key_clean in clean_name:
            score = len(os.path.commonprefix([clean_name, key_clean]))
            if score > best_score:
                best_score = score
                best_match = key

    metadata = WIITDB.get(best_match, {}) if best_match else {}
    return {
        'gcid': metadata.get('gcid', 'UNKNOWN'),
        'title': display_title
    }

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f).get('gamecube_folder')
    return None

def save_config(path):
    with open(CONFIG_FILE, 'w') as f:
        json.dump({'gamecube_folder': path}, f)

def load_external_folder():
    if os.path.exists(EXTERNAL_PATH_FILE):
        with open(EXTERNAL_PATH_FILE, 'r') as f:
            return f.read().strip()
    return None

def save_external_folder(path):
    with open(EXTERNAL_PATH_FILE, 'w') as f:
        f.write(path)

def scan_gamecube_files(folder):
    game_files = []
    for root, dirs, files in os.walk(folder):
        for file in files:
            ext = os.path.splitext(file)[1].lower()
            if ext == '.iso' and file.lower().endswith('.nkit.iso'):
                ext = '.nkit.iso'
            if ext in SUPPORTED_EXTENSIONS:
                game_files.append(os.path.join(root, file))
    return game_files

def find_closest_disc_image(gcid):
    def score(filename):
        base = os.path.splitext(filename)[0].lower()
        return len(os.path.commonprefix([gcid.lower(), base]))

    best_match = None
    best_score = 0
    for fname in os.listdir(ASSET_FOLDER):
        if fname.lower().endswith('.png'):
            current_score = score(fname)
            if current_score > best_score:
                best_score = current_score
                best_match = fname
    return os.path.join(ASSET_FOLDER, best_match) if best_match else None

def openGrid():
    grid_window = tk.Toplevel()
    grid_window.title("GameCube Game Grid Viewer")
    grid_window.geometry("1000x800")

    frame = tk.Frame(grid_window)
    frame.pack(fill='both', expand=True)

    button_frame = tk.Frame(frame)
    button_frame.pack(fill='x')

    def choose_folder():
        folder = filedialog.askdirectory(title='Select GameCube Folder')
        if folder:
            save_config(folder)
            gamecube_path_var.set(folder)
            refresh_grid(folder)

    tk.Button(button_frame, text="Choose GameCube Folder", command=choose_folder).pack(side='left', padx=10, pady=10)

    gamecube_path_var = tk.StringVar()
    gamecube_path_entry = tk.Entry(button_frame, textvariable=gamecube_path_var, width=60, state='readonly')
    gamecube_path_entry.pack(side='left', padx=10)

    canvas = Canvas(frame)
    canvas.pack(side="left", fill="both", expand=True)
    scrollbar = Scrollbar(frame, orient="vertical", command=canvas.yview)
    scrollbar.pack(side="right", fill="y")
    canvas.configure(yscrollcommand=scrollbar.set)

    scrollable_frame = Frame(canvas)
    canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")

    scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))

    def refresh_grid(rom_folder):
        for widget in scrollable_frame.winfo_children():
            widget.destroy()

        game_files = scan_gamecube_files(rom_folder)
        metadata_list = [extract_metadata(path) for path in game_files]
        metadata_list.sort(key=lambda x: x['title'].lower())

        canvas.update_idletasks()
        grid_width = canvas.winfo_width()
        columns = max(grid_width // 100, 1)

        for i, data in enumerate(metadata_list):
            gcid = data['gcid']
            image_path = os.path.join(ASSET_FOLDER, f"{gcid}.png")

            if not os.path.exists(image_path):
                image_path = find_closest_disc_image(gcid)

            if image_path and os.path.exists(image_path):
                img = Image.open(image_path).resize((100, 100))
            else:
                img = Image.new('RGB', (100, 100), (200, 200, 200))
                draw = ImageDraw.Draw(img)
                font = ImageFont.load_default()
                draw.text((10, 45), gcid, fill=(0, 0, 0), font=font)

            tk_img = ImageTk.PhotoImage(img)

            label = tk.Label(scrollable_frame, image=tk_img, width=100, height=100)
            label.image = tk_img
            row = i // columns
            col = i % columns
            label.grid(row=row, column=col, padx=1, pady=1)

    saved_path = load_config()
    if saved_path:
        gamecube_path_var.set(saved_path)
        if os.path.exists(saved_path):
            grid_window.after(100, lambda: refresh_grid(saved_path))
