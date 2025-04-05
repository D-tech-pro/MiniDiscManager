import os
import json
import shutil
import tkinter as tk
from tkinter import filedialog, ttk
import threading
import re
import time
from main_grid import openGrid

CONFIG_FILE = 'config.json'
OUTPUT_FOLDER_FILE = 'external_folder.txt'
WIITDB_FILE = 'wiitdb_parsed.json'
SUPPORTED_EXTENSIONS = ['.iso', '.gcm', '.nkit.iso']

WIITDB = {}
if os.path.exists(WIITDB_FILE):
    with open(WIITDB_FILE, 'r', encoding='utf-8') as f:
        WIITDB = json.load(f)

def clean_filename(name):
    return re.sub(r'[^a-zA-Z0-9]', '', name).lower()

def strip_region_tags(title):
    return re.sub(r'\((USA|Europe|Japan)\)', '', title, flags=re.IGNORECASE).strip()

def extract_metadata(file_path):
    filename = os.path.splitext(os.path.basename(file_path))[0]
    display_title = strip_region_tags(filename)
    clean_name = clean_filename(filename)
    file_size = os.path.getsize(file_path)
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
    input_info = metadata.get("input", {})
    controls = json.dumps(input_info.get("controls", [{"type": "gamecube", "required": True}]))
    input_players = input_info.get("players", '1')
    genre = metadata.get('genre', 'Unknown')
    genre_list = [g.strip() for g in genre.split(',')] if isinstance(genre, str) else ['Unknown']
    return {
        'gcid': metadata.get('gcid', 'UNKNOWN'),
        'title': display_title,
        'type': metadata.get('type', 'GameCube'),
        'region': region,
        'developer': metadata.get('developer', 'Unknown'),
        'publisher': metadata.get('publisher', 'Unknown'),
        'genre': genre,
        'genre_list': genre_list,
        'description': metadata.get('description', 'No description available.'),
        'release_date': metadata.get('release_date', '2000-01-01'),
        'esrb_rating': metadata.get('esrb_rating', 'Unrated'),
        'online_players': metadata.get('online_players', '0'),
        'input_players': input_players,
        'controls': controls,
        'path': file_path,
        'size': file_size
    }

def save_config(path):
    with open(CONFIG_FILE, 'w') as f:
        json.dump({'gamecube_folder': path}, f)

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f).get('gamecube_folder')
    return None

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

def choose_folder():
    folder = filedialog.askdirectory(title='Select GameCube Folder')
    if folder:
        save_config(folder)
        refresh_file_list(folder)

def choose_output_folder():
    folder = filedialog.askdirectory(title='Select Output Folder')
    if folder:
        with open(OUTPUT_FOLDER_FILE, 'w') as f:
            f.write(folder)
        output_folder_var.set(folder)
        threading.Thread(target=copy_files_with_progress, args=(folder,), daemon=True).start()

def copy_files_with_progress(output_folder):
    progress_label.config(text="Starting copy...")
    total_files = len(tree.get_children())
    for i, row_id in enumerate(tree.get_children(), 1):
        values = tree.item(row_id)['values']
        original_path = values[14]
        filename = os.path.basename(original_path)
        destination = os.path.join(output_folder, filename)
        try:
            if os.path.exists(destination):
                original_size = os.path.getsize(original_path)
                if original_size == os.path.getsize(destination):
                    tree.set(row_id, column="In External Folder", value="✅")
                    continue
            progress_label.config(text=f"Transferring {filename} ({i}/{total_files})...")
            start = time.time()
            with open(original_path, 'rb') as src, open(destination, 'wb') as dst:
                shutil.copyfileobj(src, dst)
            end = time.time()
            speed = os.path.getsize(original_path) / 1024 / 1024 / (end - start + 0.01)
            progress_label.config(text=f"{filename} ({i}/{total_files}) - {speed:.2f} MB/s")
            tree.set(row_id, column="In External Folder", value="✅")
        except Exception as e:
            progress_label.config(text=f"Error copying {filename}: {e}")
            continue
    progress_label.config(text="Copy completed.")

def update_transfer_status_column(external_folder):
    for row_id in tree.get_children():
        values = tree.item(row_id)['values']
        path = values[14]
        filename = os.path.basename(path)
        destination_path = os.path.join(external_folder, filename)
        if os.path.exists(destination_path) and os.path.getsize(destination_path) == os.path.getsize(path):
            tree.set(row_id, column="In External Folder", value="✅")
        else:
            tree.set(row_id, column="In External Folder", value="")

def choose_existing_external_folder():
    folder = filedialog.askdirectory(title='Select External Folder to Check')
    if folder:
        with open(OUTPUT_FOLDER_FILE, 'w') as f:
            f.write(folder)
        output_folder_var.set(folder)
        update_transfer_status_column(folder)

def sort_by_column(treeview, col, descending):
    data = [(treeview.set(child, col), child) for child in treeview.get_children('')]
    data.sort(reverse=descending)
    for idx, item in enumerate(data):
        treeview.move(item[1], '', idx)
    treeview.heading(col, command=lambda: sort_by_column(treeview, col, not descending))

def refresh_file_list(folder):
    game_files = scan_gamecube_files(folder)
    all_metadata.clear()
    for row in tree.get_children():
        tree.delete(row)
    for game_path in game_files:
        metadata = extract_metadata(game_path)
        all_metadata.append(metadata)
    apply_filters()

def apply_filters():
    for row in tree.get_children():
        tree.delete(row)

    selected_players = {p for p, var in player_filters.items() if var.get()}
    selected_regions = {r for r, var in region_filters.items() if var.get()}
    selected_genres = {g for g, var in genre_filters.items() if var.get()}

    folder = output_folder_var.get()
    disney_enabled = disney_filter.get()
    nick_enabled = nick_filter.get()
    brands_checked = []
    if disney_enabled:
        brands_checked.append("disney")
    if nick_enabled:
        brands_checked.append("nickelodeon")

    filtered = []
    total_gb = 0

    for m in all_metadata:
        if m['input_players'] not in selected_players:
            continue
        if m['region'] not in selected_regions:
            continue
        if selected_genres and not any(g in selected_genres for g in m.get('genre_list', [])):
            continue

        title_lower = m['title'].lower()
        if not disney_filter.get() and title_lower.startswith("disney"):
            continue
        if not nick_filter.get() and title_lower.startswith("nickelodeon"):
            continue




        exists = "✅" if folder and os.path.exists(os.path.join(folder, os.path.basename(m['path']))) and os.path.getsize(os.path.join(folder, os.path.basename(m['path']))) == m['size'] else ""

        # Games List filter
        if not include_main_folder.get() and exists == "":
            continue
        if not include_external_folder.get() and exists == "✅":
            continue

        filtered.append((m, exists))
        total_gb += m['size']

    for metadata, exists in filtered:
        tree.insert('', 'end', values=(
            exists, metadata['gcid'], metadata['title'], metadata['type'], metadata['region'],
            metadata['developer'], metadata['publisher'], metadata['genre'],
            metadata['description'], metadata['release_date'], metadata['esrb_rating'],
            metadata['online_players'], metadata['input_players'], metadata['controls'],
            metadata['path'], f"{metadata['size'] / (1024**3):.2f} GB"
        ))

    count_label.config(text=f"Filtered Games: {len(filtered)} | Total Size: {total_gb / (1024**3):.2f} GB")

root = tk.Tk()
root.title("GameCube Game Manager")
root.geometry("1500x900")

frame = tk.Frame(root)
frame.pack(fill='both', expand=True, padx=10, pady=10)

output_folder_var = tk.StringVar()
if os.path.exists(OUTPUT_FOLDER_FILE):
    with open(OUTPUT_FOLDER_FILE, 'r') as f:
        output_folder_var.set(f.read().strip())

tk.Label(frame, text="External Folder Path:").pack(anchor='w')
tk.Entry(frame, textvariable=output_folder_var, width=100).pack(fill='x')

filter_frame = tk.LabelFrame(frame, text="Filters")
filter_frame.pack(fill='x', pady=5)

filter_column_frame = tk.Frame(filter_frame)
filter_column_frame.pack(fill='x')

# --- Players ---
player_column = tk.Frame(filter_column_frame)
player_column.pack(side='left', padx=10)
tk.Label(player_column, text="Players").pack(anchor='w')
player_filters = {}
for p in ['0', '1', '2', '4']:
    var = tk.BooleanVar(value=True)
    tk.Checkbutton(player_column, text=p, variable=var, command=apply_filters).pack(anchor='w')
    player_filters[p] = var

# --- Vertical Separator ---
ttk.Separator(filter_column_frame, orient='vertical').pack(side='left', fill='y', padx=5)

# --- Region ---
region_column = tk.Frame(filter_column_frame)
region_column.pack(side='left', padx=10)
tk.Label(region_column, text="Region").pack(anchor='w')
region_filters = {}
for r in ['NTSC-U', 'PAL', 'NTSC-J', 'Unknown']:
    var = tk.BooleanVar(value=True)
    tk.Checkbutton(region_column, text=r, variable=var, command=apply_filters).pack(anchor='w')
    region_filters[r] = var

# --- Vertical Separator ---
ttk.Separator(filter_column_frame, orient='vertical').pack(side='left', fill='y', padx=5)

# --- Brands ---
brand_column = tk.Frame(filter_column_frame)
brand_column.pack(side='left', padx=10)
tk.Label(brand_column, text="Brands").pack(anchor='w')
disney_filter = tk.BooleanVar(value=True)
nick_filter = tk.BooleanVar(value=True)
tk.Checkbutton(brand_column, text="Disney", variable=disney_filter, command=apply_filters).pack(anchor='w')
tk.Checkbutton(brand_column, text="Nickelodeon", variable=nick_filter, command=apply_filters).pack(anchor='w')
ttk.Separator(filter_column_frame, orient='vertical').pack(side='left', fill='y', padx=5)

# --- Games List Filter ---
gameslist_column = tk.Frame(filter_column_frame)
gameslist_column.pack(side='left', padx=10)
tk.Label(gameslist_column, text="Games List").pack(anchor='w')
include_main_folder = tk.BooleanVar(value=True)
include_external_folder = tk.BooleanVar(value=True)
tk.Checkbutton(gameslist_column, text="Main Folder", variable=include_main_folder, command=apply_filters).pack(anchor='w')
tk.Checkbutton(gameslist_column, text="External Folder", variable=include_external_folder, command=apply_filters).pack(anchor='w')

# --- Horizontal Separator before Genre ---
ttk.Separator(filter_frame, orient='horizontal').pack(fill='x', pady=10)

# --- Genres ---
genre_column = tk.Frame(filter_frame)
genre_column.pack(fill='x')
tk.Label(genre_column, text="Genre").pack(anchor='w')

genre_set = set()
for entry in WIITDB.values():
    if 'genre' in entry and isinstance(entry['genre'], str):
        for g in entry['genre'].split(','):
            genre_set.add(g.strip())
all_genres = sorted(genre_set)

genre_filters = {}
rows_per_column = 5
genre_columns = []
for i in range((len(all_genres) + rows_per_column - 1) // rows_per_column):
    col = tk.Frame(genre_column)
    col.pack(side='left', padx=5)
    genre_columns.append(col)

for i, g in enumerate(all_genres):
    var = tk.BooleanVar(value=False)
    col_index = i // rows_per_column
    tk.Checkbutton(genre_columns[col_index], text=g, variable=var, command=apply_filters).pack(anchor='w')
    genre_filters[g] = var


count_label = tk.Label(filter_frame, text="Filtered Games: 0 | Total Size: 0.00 GB")
count_label.pack(side='bottom', pady=5)

button_frame = tk.Frame(frame)
button_frame.pack(fill='x', pady=5)

tk.Button(button_frame, text="Choose Folder", command=choose_folder).pack(side='left')
tk.Button(button_frame, text="Copy Displayed Files to Folder", command=choose_output_folder).pack(side='left', padx=10)
tk.Button(button_frame, text="Check External Folder", command=choose_existing_external_folder).pack(side='left', padx=10)
tk.Button(button_frame, text="Open Grid", command=openGrid).pack(side='left', padx=10)
progress_label = tk.Label(button_frame, text="")
progress_label.pack(side='left', padx=10)

columns = [
    'In External Folder', 'GameCube ID', 'Game Title', 'Console', 'Region', 'Developer', 'Publisher', 'genre',
    'Game Description', 'Release Date', 'ESRB Rating', 'online_players',
    'Max Players', 'Controls', 'path', 'size'
]
tree = ttk.Treeview(frame, columns=columns, show='headings')
for col in columns:
    tree.heading(col, text=col, command=lambda _col=col: sort_by_column(tree, _col, False))
    tree.column(col, width=120, anchor='w')
tree_scrollbar = ttk.Scrollbar(frame, orient='vertical', command=tree.yview)
tree.configure(yscrollcommand=tree_scrollbar.set)
tree.pack(side='left', fill='both', expand=True)
tree_scrollbar.pack(side='right', fill='y')

all_metadata = []
saved_path = load_config()
if saved_path and os.path.exists(saved_path):
    refresh_file_list(saved_path)

root.mainloop()
