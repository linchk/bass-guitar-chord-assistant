import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext, Menu
import re
import yaml
import webbrowser
import os
import tempfile
from collections import Counter
from functools import lru_cache
from enum import Enum

# Note mapping and music theory data
NOTE_TO_PITCH = {
    'C': 0, 'C#': 1, 'Db': 1, 'D': 2, 'D#': 3, 'Eb': 3, 'E': 4, 'F': 5,
    'F#': 6, 'Gb': 6, 'G': 7, 'G#': 8, 'Ab': 8, 'A': 9, 'A#': 10, 'Bb': 10, 'B': 11
}

PITCH_TO_NOTE_SHARP = {
    0: 'C', 1: 'C#', 2: 'D', 3: 'D#', 4: 'E', 5: 'F',
    6: 'F#', 7: 'G', 8: 'G#', 9: 'A', 10: 'A#', 11: 'B'
}

PITCH_TO_NOTE_FLAT = {
    0: 'C', 1: 'Db', 2: 'D', 3: 'Eb', 4: 'E', 5: 'F',
    6: 'Gb', 7: 'G', 8: 'Ab', 9: 'A', 10: 'Bb', 11: 'B'
}

CHORD_FORMULAS = {
    '': [0, 4, 7],              # Major
    'm': [0, 3, 7],             # Minor
    '7': [0, 4, 7, 10],         # Dominant 7th
    'm7': [0, 3, 7, 10],        # Minor 7th
    'maj7': [0, 4, 7, 11],      # Major 7th
    'dim': [0, 3, 6],           # Diminished
    'dim7': [0, 3, 6, 9],       # Diminished 7th
    'aug': [0, 4, 8],           # Augmented
    '+': [0, 4, 8],             # Augmented
    'sus4': [0, 5, 7],          # Suspended 4th
    'sus2': [0, 2, 7],          # Suspended 2nd
    '6': [0, 4, 7, 9],          # Added 6th
    '7sus4': [0, 5, 7, 10],     # 7th suspended 4th
    'm7b5': [0, 3, 6, 10],      # Half-diminished
}

SCALE_DEGREES_MAJOR = ['I', 'ii', 'iii', 'IV', 'V', 'vi', 'vii°']
SCALE_DEGREES_MINOR = ['i', 'ii°', 'III', 'iv', 'v', 'VI', 'VII']

# Bass string tunings
BASS_TUNINGS = {
    4: [('G', 55), ('D', 50), ('A', 45), ('E', 40)],  # Standard 4-string bass (G-D-A-E)
    5: [('G', 55), ('D', 50), ('A', 45), ('E', 40), ('B', 35)]  # 5-string bass (G-D-A-E-B)
}

FRETS = 5  # Number of frets to display in diagram

class NoteType(Enum):
    BASS_NOTE = 1
    CHORD_NOTE = 2
    NOT_IN_CHORD = 3

class DisplayMode(Enum):
    STANDARD = 1  # B for bass, X for other chord notes
    EDUCATIONAL = 2  # Letter names for all notes

class StringCount(Enum):
    FOUR_STRINGS = 4
    FIVE_STRINGS = 5

class Chord:
    def __init__(self, symbol, section=""):
        self.symbol = symbol.strip()
        self.section = section
        self.root = ""
        self.bass_note = ""
        self.suffix = ""
        self.parse()
    
    def parse(self):
        # Handle slash chords (e.g., C/E)
        if '/' in self.symbol:
            parts = self.symbol.split('/')
            chord_part = parts[0].strip()
            self.bass_note = parts[1].strip()
        else:
            chord_part = self.symbol
            self.bass_note = None
        
        # Extract root note (A-G with optional accidental)
        match = re.match(r'^([A-G][#b]?)', chord_part)
        if match:
            self.root = match.group(1)
            self.suffix = chord_part[len(self.root):].lower().strip()
        else:
            # Fallback for chords that don't start with A-G
            self.root = chord_part[0] if chord_part else ""
            self.suffix = chord_part[1:].lower().strip() if len(chord_part) > 1 else ""
        
        # If no explicit bass note, use root
        if self.bass_note is None or not self.bass_note:
            self.bass_note = self.root

class Song:
    def __init__(self, title="", author="", key=None):
        self.title = title
        self.author = author
        self.key = key
        self.chords = []  # List of Chord objects
    
    def add_chord(self, chord, section):
        if chord.strip():  # Only add non-empty chords
            self.chords.append(Chord(chord, section))
    
    def detect_key(self):
        """Detect the key of the song based on chord analysis"""
        if not self.chords:
            return "C"
        
        # Get all root notes
        roots = [chord.root for chord in self.chords if chord.root]
        
        if not roots:
            return "C"
        
        # Count frequency of each root
        root_counts = Counter(roots)
        
        # Get most common root
        most_common_root = root_counts.most_common(1)[0][0]
        
        # Check if minor (look for 'm' suffix but not 'maj' or 'dim')
        is_minor = False
        for chord in self.chords:
            if chord.root == most_common_root:
                if 'm' in chord.suffix and 'maj' not in chord.suffix and 'dim' not in chord.suffix:
                    is_minor = True
                    break
        
        return most_common_root + ('m' if is_minor else '')

class BassCard:
    def __init__(self, chord, key, string_count=4):
        self.chord = chord
        self.key = key
        self.string_count = string_count
        self.scale_degree = self._get_scale_degree()
        self.notes = self._get_chord_notes()
        self.note_pitches = self._get_chord_note_pitches()
        self.bass_pitch = NOTE_TO_PITCH.get(chord.bass_note, 0)
        self.fretboard = self._generate_fretboard()
    
    def _get_scale_degree(self):
        """Determine the scale degree of the chord root in the given key"""
        if not self.key or not self.chord.root:
            return "?"
        
        # Determine if key is minor
        is_minor_key = 'm' in self.key and 'maj' not in self.key and 'dim' not in self.key
        
        # Get root pitch classes
        key_root_match = re.match(r'^([A-G][#b]?)', self.key)
        key_root = key_root_match.group(1) if key_root_match else 'C'
        key_pitch = NOTE_TO_PITCH.get(key_root, 0)
        
        root_pitch = NOTE_TO_PITCH.get(self.chord.root, 0)
        
        # Calculate scale degree
        degree = (root_pitch - key_pitch) % 12
        
        # Map to scale degree based on key type
        if is_minor_key:
            scale_degrees = SCALE_DEGREES_MINOR
        else:
            scale_degrees = SCALE_DEGREES_MAJOR
        
        # Handle enharmonic equivalents and common degrees
        if degree == 0:
            return scale_degrees[0]
        elif degree == 2:
            return scale_degrees[1]
        elif degree == 4:
            return scale_degrees[2]
        elif degree == 5:
            return scale_degrees[3]
        elif degree == 7:
            return scale_degrees[4]
        elif degree == 9:
            return scale_degrees[5]
        elif degree == 11:
            return scale_degrees[6]
        
        return f"? ({degree})"
    
    def _get_chord_notes(self):
        """Get the notes that make up this chord"""
        if not self.chord.root:
            return ["?"]
        
        root_pitch = NOTE_TO_PITCH.get(self.chord.root, 0)
        
        # Determine chord formula
        formula = CHORD_FORMULAS.get(self.chord.suffix, CHORD_FORMULAS[''])
        
        # Calculate note pitches
        note_pitches = [(root_pitch + interval) % 12 for interval in formula]
        
        # Determine note naming convention based on key
        if any(accidental in self.key for accidental in ['#', 'm']) or '#' in self.chord.root:
            pitch_to_note = PITCH_TO_NOTE_SHARP
        else:
            pitch_to_note = PITCH_TO_NOTE_FLAT
        
        # Convert pitches to note names
        notes = [pitch_to_note[p] for p in note_pitches]
        return notes
    
    def _get_chord_note_pitches(self):
        """Get the pitch classes of notes in this chord"""
        if not self.chord.root:
            return []
        
        root_pitch = NOTE_TO_PITCH.get(self.chord.root, 0)
        formula = CHORD_FORMULAS.get(self.chord.suffix, CHORD_FORMULAS[''])
        return [(root_pitch + interval) % 12 for interval in formula]
    
    def _generate_fretboard(self):
        """Generate fretboard diagram showing all chord notes positions"""
        # Get all chord note pitch classes
        chord_pitches = self.note_pitches
        
        # Determine bass note pitch class
        bass_pitch_class = self.bass_pitch
        
        # Get the appropriate string tuning
        bass_strings = BASS_TUNINGS[self.string_count]
        
        # Generate grid for fretboard
        grid = []
        for string_name, base_pitch in bass_strings:
            row = []
            for fret in range(FRETS + 1):
                note_pitch = (base_pitch + fret) % 12
                
                # Determine appropriate note name based on context
                if any(accidental in self.key for accidental in ['#', 'm']) or '#' in self.chord.root:
                    note_name = PITCH_TO_NOTE_SHARP[note_pitch]
                else:
                    note_name = PITCH_TO_NOTE_FLAT[note_pitch]
                
                if note_pitch == bass_pitch_class:
                    row.append((NoteType.BASS_NOTE, note_name))  # Bass note
                elif note_pitch in chord_pitches:
                    row.append((NoteType.CHORD_NOTE, note_name))  # Other chord note
                else:
                    row.append((NoteType.NOT_IN_CHORD, note_name))  # Not in chord
            grid.append((string_name, row))
        return grid
    
    def get_note_at_position(self, string_idx, fret):
        """Get note information at specific position"""
        if 0 <= string_idx < len(self.fretboard) and 0 <= fret <= FRETS:
            _, markers = self.fretboard[string_idx]
            return markers[fret]
        return (NoteType.NOT_IN_CHORD, "?")

class BassChordApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Bass Guitar Chord Assistant")
        self.root.geometry("1200x700")
        
        # Song data
        self.song = Song()
        self.cards = []
        self.columns_for_export = tk.IntVar(value=1)
        self.display_mode = tk.IntVar(value=DisplayMode.STANDARD.value)
        self.string_count = tk.IntVar(value=StringCount.FOUR_STRINGS.value)
        
        # Create menu bar
        self.create_menu_bar()
        
        # Create widgets
        self.create_widgets()
        
        # Load settings
        self.load_settings()
        
        # Generate help file
        self.generate_help_file()
    
    def create_menu_bar(self):
        """Create the menu bar for the application"""
        menubar = Menu(self.root)
        
        # File menu
        file_menu = Menu(menubar, tearoff=0)
        file_menu.add_command(label="Load Song", command=self.load_song)
        file_menu.add_command(label="Save Cards", command=self.save_cards)
        file_menu.add_command(label="Load Cards", command=self.load_cards)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.quit)
        menubar.add_cascade(label="File", menu=file_menu)
        
        # Edit menu
        edit_menu = Menu(menubar, tearoff=0)
        edit_menu.add_command(label="Copy", command=lambda: self.song_text.event_generate("<<Copy>>"))
        edit_menu.add_command(label="Cut", command=lambda: self.song_text.event_generate("<<Cut>>"))
        edit_menu.add_command(label="Paste", command=lambda: self.song_text.event_generate("<<Paste>>"))
        edit_menu.add_separator()
        edit_menu.add_command(label="Select All", command=lambda: self.song_text.event_generate("<<SelectAll>>"))
        menubar.add_cascade(label="Edit", menu=edit_menu)
        
        # View menu
        view_menu = Menu(menubar, tearoff=0)
        
        # Display mode submenu
        display_mode_menu = Menu(view_menu, tearoff=0)
        display_mode_menu.add_radiobutton(label="Standard Mode (B/X)", 
                                          variable=self.display_mode, 
                                          value=DisplayMode.STANDARD.value,
                                          command=self.display_cards)
        display_mode_menu.add_radiobutton(label="Educational Mode (Note Names)", 
                                          variable=self.display_mode, 
                                          value=DisplayMode.EDUCATIONAL.value,
                                          command=self.display_cards)
        view_menu.add_cascade(label="Display Mode", menu=display_mode_menu)
        
        # String count submenu
        string_count_menu = Menu(view_menu, tearoff=0)
        string_count_menu.add_radiobutton(label="4-String Bass", 
                                          variable=self.string_count, 
                                          value=StringCount.FOUR_STRINGS.value,
                                          command=self.display_cards)
        string_count_menu.add_radiobutton(label="5-String Bass", 
                                          variable=self.string_count, 
                                          value=StringCount.FIVE_STRINGS.value,
                                          command=self.display_cards)
        view_menu.add_cascade(label="Bass Type", menu=string_count_menu)
        
        menubar.add_cascade(label="View", menu=view_menu)
        
        # Export menu
        export_menu = Menu(menubar, tearoff=0)
        export_menu.add_command(label="Export HTML", command=self.export_html)
        export_menu.add_command(label="Print Cards", command=self.print_cards)
        menubar.add_cascade(label="Export", menu=export_menu)
        
        # Help menu
        help_menu = Menu(menubar, tearoff=0)
        help_menu.add_command(label="User Guide", command=self.show_help)
        help_menu.add_command(label="About", command=self.show_about)
        menubar.add_cascade(label="Help", menu=help_menu)
        
        self.root.config(menu=menubar)
    
    def create_widgets(self):
        # Main frame with paned window for side-by-side layout
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Create paned window for side-by-side layout
        paned_window = ttk.PanedWindow(main_frame, orient=tk.HORIZONTAL)
        paned_window.pack(fill=tk.BOTH, expand=True)
        
        # Left frame for song input and controls
        left_frame = ttk.Frame(paned_window)
        paned_window.add(left_frame, weight=1)
        
        # Right frame for bass cards
        right_frame = ttk.Frame(paned_window)
        paned_window.add(right_frame, weight=1)
        
        # Top frame for metadata
        top_frame = ttk.Frame(left_frame)
        top_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Title input
        ttk.Label(top_frame, text="Title:").grid(row=0, column=0, sticky=tk.W, padx=(0, 5))
        self.title_var = tk.StringVar()
        title_entry = ttk.Entry(top_frame, textvariable=self.title_var, width=40)
        title_entry.grid(row=0, column=1, sticky=tk.EW)
        
        # Author input
        ttk.Label(top_frame, text="Author:").grid(row=0, column=2, sticky=tk.W, padx=(10, 5))
        self.author_var = tk.StringVar()
        author_entry = ttk.Entry(top_frame, textvariable=self.author_var, width=30)
        author_entry.grid(row=0, column=3, sticky=tk.EW)
        
        top_frame.columnconfigure(1, weight=1)
        top_frame.columnconfigure(3, weight=1)
        
        # Song text area
        text_frame = ttk.LabelFrame(left_frame, text="Song Chord Chart")
        text_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # Ensure the text widget is enabled for input
        self.song_text = scrolledtext.ScrolledText(text_frame, wrap=tk.WORD, font=("Courier", 10))
        self.song_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Control buttons
        btn_frame = ttk.Frame(left_frame)
        btn_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Button(btn_frame, text="Load Song", command=self.load_song).pack(side=tk.LEFT, padx=5, pady=5)
        ttk.Button(btn_frame, text="Analyze Chords", command=self.analyze_chords).pack(side=tk.LEFT, padx=5, pady=5)
        ttk.Button(btn_frame, text="Save Cards", command=self.save_cards).pack(side=tk.LEFT, padx=5, pady=5)
        ttk.Button(btn_frame, text="Load Cards", command=self.load_cards).pack(side=tk.LEFT, padx=5, pady=5)
        
        # Export options frame
        export_frame = ttk.LabelFrame(left_frame, text="Export Options")
        export_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(export_frame, text="Columns for print/export:").grid(row=0, column=0, padx=5, pady=5)
        columns_combo = ttk.Combobox(export_frame, textvariable=self.columns_for_export, 
                                   values=[1, 2, 3, 4], width=5, state="readonly")
        columns_combo.grid(row=0, column=1, padx=5, pady=5)
        columns_combo.current(0)
        
        ttk.Button(export_frame, text="Export HTML", command=self.export_html).grid(row=0, column=2, padx=10, pady=5)
        ttk.Button(export_frame, text="Print Cards", command=self.print_cards).grid(row=0, column=3, padx=5, pady=5)
        
        # Cards display area (right side)
        cards_frame = ttk.LabelFrame(right_frame, text="Bass Chord Cards")
        cards_frame.pack(fill=tk.BOTH, expand=True)
        
        # Scrollable canvas for cards
        self.canvas = tk.Canvas(cards_frame)
        scrollbar = ttk.Scrollbar(cards_frame, orient=tk.VERTICAL, command=self.canvas.yview)
        self.cards_container = ttk.Frame(self.canvas)
        
        self.cards_container.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )
        
        self.canvas_frame = self.canvas.create_window((0, 0), window=self.cards_container, anchor="nw")
        self.canvas.configure(yscrollcommand=scrollbar.set)
        
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Bind mouse wheel to canvas scrolling
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)
    
    def _on_mousewheel(self, event):
        self.canvas.yview_scroll(int(-1*(event.delta/120)), "units")
    
    def load_settings(self):
        """Load application settings"""
        # This is a placeholder for loading settings from a config file
        pass
    
    def generate_help_file(self):
        """Generate the help HTML file"""
        help_content = """
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Bass Guitar Chord Assistant - User Guide</title>
            <style>
                body {
                    font-family: Arial, sans-serif;
                    line-height: 1.6;
                    margin: 40px;
                    color: #333;
                }
                h1 {
                    color: #2c3e50;
                    text-align: center;
                }
                h2 {
                    color: #3498db;
                    border-bottom: 1px solid #eee;
                    padding-bottom: 5px;
                }
                .section {
                    margin-bottom: 25px;
                }
                .example {
                    background-color: #f8f9fa;
                    border: 1px solid #ddd;
                    padding: 15px;
                    border-radius: 5px;
                    margin: 15px 0;
                    font-family: monospace;
                    white-space: pre-wrap;
                }
                .tip {
                    background-color: #e8f4f8;
                    border-left: 4px solid #3498db;
                    padding: 10px 15px;
                    margin: 15px 0;
                }
                .note {
                    background-color: #fff8e1;
                    border-left: 4px solid #ffc107;
                    padding: 10px 15px;
                    margin: 15px 0;
                }
                table {
                    border-collapse: collapse;
                    width: 100%;
                    margin: 15px 0;
                }
                th, td {
                    border: 1px solid #ddd;
                    padding: 8px;
                    text-align: left;
                }
                th {
                    background-color: #f2f2f2;
                }
                code {
                    background-color: #f1f1f1;
                    padding: 2px 6px;
                    border-radius: 3px;
                    font-family: monospace;
                }
            </style>
        </head>
        <body>
            <h1>Bass Guitar Chord Assistant</h1>
            <p>A comprehensive tool for analyzing chord charts and generating bass guitar chord diagrams.</p>
            
            <div class="section">
                <h2>Getting Started</h2>
                <p>To use the Bass Guitar Chord Assistant:</p>
                <ol>
                    <li>Enter or load a song with chords</li>
                    <li>Set the song title and author</li>
                    <li>Click "Analyze Chords" to generate bass chord cards</li>
                    <li>View, export, or print the chord cards as needed</li>
                </ol>
            </div>
            
            <div class="section">
                <h2>Song Format Requirements</h2>
                <p>The program requires a specific format for song files to correctly identify chords:</p>
                
                <div class="tip">
                    <strong>Important:</strong> Chord lines MUST start with a dot (.) character followed by the chord symbols.
                </div>
                
                <h3>Section Headers</h3>
                <p>Sections are marked with square brackets, for example:</p>
                <div class="example">
[V1]
[Chorus]
[Bridge]
[P1]
[C1]
                </div>
                
                <h3>Chord Lines</h3>
                <p>Each line containing chords must begin with a dot (.) followed by the chord symbols. Chord symbols can be separated by spaces or tabs.</p>
                
                <h3>Example Song File</h3>
                <div class="example">
[V1]
.Em
 Рухнул мир, сгорел дотла,
.   C            B
 Соблазны рвут тебя на части:
.Em                        C
 Смертный страх и жажда зла
.         B
 Держат пари.
.  Em
 В темноте рычит зверьё,
.   C               B
 Не видно глаз, но всё в их власти,
.Em                       C
 Стань таким, возьми своё,
.      B
 Или умри.

[P1]
.Am         C           F#    F#7
 Будь наготове, всюду рыщет стража,
.Am      C            D   B7
 Линия крови путь тебе укажет:

[C1]
.Em              Am7
 Прочь, ты был одним из нас.
.Em           Am7
 Но ангел тебя не спас…
                </div>
                
                <div class="note">
                    <strong>Note:</strong> The dot at the beginning of chord lines is crucial for the program to identify chords properly. Without it, the chords will not be recognized.
                </div>
            </div>
            
            <div class="section">
                <h2>Display Modes</h2>
                <p>The program offers two display modes for chord diagrams:</p>
                
                <h3>Standard Mode (B/X)</h3>
                <ul>
                    <li><code>B</code> - Bass note (with red background)</li>
                    <li><code>X</code> - Other chord notes (with blue background)</li>
                    <li><code>.</code> - Notes not in the chord</li>
                </ul>
                
                <h3>Educational Mode (Note Names)</h3>
                <ul>
                    <li>Actual note names (C, C#, D, etc.) are displayed</li>
                    <li>Bass note has red background and bold text</li>
                    <li>Other chord notes have blue background and bold text</li>
                    <li>Notes not in the chord are shown as <code>.</code></li>
                </ul>
            </div>
            
            <div class="section">
                <h2>Bass Guitar Types</h2>
                <p>You can switch between two bass guitar configurations:</p>
                <ul>
                    <li><strong>4-String Bass</strong> - Standard tuning (G-D-A-E, from highest to lowest pitch)</li>
                    <li><strong>5-String Bass</strong> - Extended range with low B string (G-D-A-E-B)</li>
                </ul>
            </div>
            
            <div class="section">
                <h2>Export Options</h2>
                <p>The program supports multiple export formats:</p>
                
                <h3>HTML Export</h3>
                <p>Export chord cards to an HTML file that can be viewed in any web browser. You can choose the number of columns (1-4) for the layout.</p>
                
                <h3>Printing</h3>
                <p>Print chord cards directly to a printer. The print layout is optimized for A4 paper and supports multiple columns.</p>
                
                <h3>YAML Format</h3>
                <p>Save and load chord analysis in YAML format, preserving all settings and analysis data.</p>
            </div>
            
            <div class="section">
                <h2>Keyboard Shortcuts</h2>
                <table>
                    <tr>
                        <th>Shortcut</th>
                        <th>Action</th>
                    </tr>
                    <tr>
                        <td>Ctrl+C</td>
                        <td>Copy selected text</td>
                    </tr>
                    <tr>
                        <td>Ctrl+X</td>
                        <td>Cut selected text</td>
                    </tr>
                    <tr>
                        <td>Ctrl+V</td>
                        <td>Paste text from clipboard</td>
                    </tr>
                    <tr>
                        <td>Ctrl+A</td>
                        <td>Select all text</td>
                    </tr>
                </table>
            </div>
            
            <div class="section">
                <h2>Troubleshooting</h2>
                <ul>
                    <li><strong>Chords not being recognized:</strong> Ensure chord lines start with a dot (.) character</li>
                    <li><strong>Incorrect key detection:</strong> Manually set the key if automatic detection fails</li>
                    <li><strong>Display issues:</strong> Try switching between display modes or adjusting the number of columns for export</li>
                </ul>
            </div>
            
            <div class="section">
                <h2>About</h2>
                <p>Bass Guitar Chord Assistant v1.0</p>
                <p>Developed to help bass guitarists understand and visualize chord structures within songs.</p>
            </div>
        </body>
        </html>
        """
        
        # Save help file to temporary location
        self.help_file_path = os.path.join(tempfile.gettempdir(), "bass_chord_assistant_help.html")
        with open(self.help_file_path, 'w', encoding='utf-8') as f:
            f.write(help_content)
    
    def show_help(self):
        """Open the help file in the default web browser"""
        try:
            webbrowser.open_new_tab(f'file://{os.path.abspath(self.help_file_path)}')
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open help file: {str(e)}")
    
    def show_about(self):
        """Show about dialog"""
        about_text = """
        Bass Guitar Chord Assistant
        Version 1.0
        
        A tool for analyzing chord charts and 
        generating bass guitar chord diagrams.
        
        Features:
        - Automatic chord and key detection
        - 4-string and 5-string bass support
        - Standard and educational display modes
        - HTML export and printing capabilities
        - Save/load analysis in YAML format
        
        Developed with Python and Tkinter
        """
        messagebox.showinfo("About", about_text)
    
    def load_song(self):
        file_path = filedialog.askopenfilename(
            title="Select Song File",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )
        if not file_path:
            return
        
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                content = file.read()
                self.song_text.delete(1.0, tk.END)
                self.song_text.insert(tk.END, content)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load file: {str(e)}")
    
    def analyze_chords(self):
        # Get song metadata
        self.song.title = self.title_var.get()
        self.song.author = self.author_var.get()
        
        # Get song text
        song_text = self.song_text.get(1.0, tk.END)
        
        # Clear existing chords
        self.song.chords = []
        
        # Parse song text
        current_section = ""
        lines = song_text.split('\n')
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Check for section headers [V1], [Chorus], etc.
            if re.match(r'^\[.*\]$', line):
                current_section = line[1:-1].strip()
                continue
            
            # Process chord lines (starting with .)
            if line.startswith('.'):
                # Remove the leading dot and split into chord tokens
                chord_line = line[1:].strip()
                # Split by whitespace but preserve multi-character chords
                chord_tokens = re.findall(r'\S+', chord_line)
                
                for token in chord_tokens:
                    if token.strip():  # Skip empty tokens
                        self.song.add_chord(token, current_section)
        
        # Detect key if not already set
        if not self.song.key:
            self.song.key = self.song.detect_key()
        
        # Generate bass cards
        self.cards = [
            BassCard(chord, self.song.key, self.string_count.get()) 
            for chord in self.song.chords
        ]
        
        # Display cards
        self.display_cards()
    
    def display_cards(self):
        # Clear existing cards
        for widget in self.cards_container.winfo_children():
            widget.destroy()
        
        if not self.cards:
            ttk.Label(self.cards_container, text="No chords analyzed yet. Load a song and click 'Analyze Chords'.").pack(pady=20)
            return
        
        # Display song metadata
        meta_frame = ttk.Frame(self.cards_container)
        meta_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Label(meta_frame, text=f"Title: {self.song.title}", font=("Arial", 10, "bold")).pack(anchor=tk.W)
        ttk.Label(meta_frame, text=f"Author: {self.song.author}", font=("Arial", 10, "bold")).pack(anchor=tk.W)
        ttk.Label(meta_frame, text=f"Key: {self.song.key}", font=("Arial", 10, "bold")).pack(anchor=tk.W)
        ttk.Label(meta_frame, text=f"Bass Type: {self.string_count.get()}-string", font=("Arial", 10, "bold")).pack(anchor=tk.W)
        
        # Display cards
        for i, card in enumerate(self.cards):
            try:
                card_frame = ttk.LabelFrame(self.cards_container, text=f"Chord: {card.chord.symbol} (Section: {card.chord.section})")
                card_frame.pack(fill=tk.X, padx=10, pady=5)
                
                # Chord details
                details_frame = ttk.Frame(card_frame)
                details_frame.pack(fill=tk.X, padx=10, pady=5)
                
                ttk.Label(details_frame, text=f"Scale Degree: {card.scale_degree}", font=("Arial", 9, "bold")).grid(row=0, column=0, sticky=tk.W)
                ttk.Label(details_frame, text=f"Bass Note: {card.chord.bass_note}", font=("Arial", 9, "bold")).grid(row=0, column=1, sticky=tk.W, padx=(20, 0))
                ttk.Label(details_frame, text=f"Chord Notes: {', '.join(card.notes)}", font=("Arial", 9)).grid(row=1, column=0, columnspan=2, sticky=tk.W, pady=(5, 0))
                
                # Fretboard diagram
                diagram_frame = ttk.Frame(card_frame)
                diagram_frame.pack(padx=10, pady=5)
                
                current_mode = DisplayMode(self.display_mode.get())
                
                # Create fretboard with visual separation between open strings and frets
                for row, (string_name, markers) in enumerate(card.fretboard):
                    # String label
                    ttk.Label(diagram_frame, text=string_name, font=("Arial", 8, "bold"), width=2).grid(row=row, column=0, padx=(0, 5))
                    
                    # Open string (0th fret) - visually separated
                    note_type, note_name = markers[0]
                    cell_text = self._get_marker_text(note_type, note_name, current_mode)
                    cell_width = 4 if current_mode == DisplayMode.EDUCATIONAL else 3
                    
                    cell = ttk.Label(diagram_frame, text=cell_text, 
                                   font=("Arial", 9, "bold" if note_type != NoteType.NOT_IN_CHORD else "normal"),
                                   width=cell_width, relief=tk.RAISED, borderwidth=2)
                    self._apply_marker_style(cell, note_type, current_mode)
                    cell.grid(row=row, column=1, padx=1, pady=1)
                    
                    # Vertical separator line - using a label instead of Separator for better compatibility
                    sep = ttk.Label(diagram_frame, text="|", font=("Arial", 9), width=1)
                    sep.grid(row=row, column=2, padx=2)
                    
                    # Frets 1-5
                    for col_index, (note_type, note_name) in enumerate(markers[1:], start=3):
                        cell_text = self._get_marker_text(note_type, note_name, current_mode)
                        cell = ttk.Label(diagram_frame, text=cell_text, 
                                       font=("Arial", 9, "bold" if note_type != NoteType.NOT_IN_CHORD else "normal"),
                                       width=cell_width, relief=tk.RAISED)
                        self._apply_marker_style(cell, note_type, current_mode)
                        cell.grid(row=row, column=col_index, padx=1, pady=1)
                
                # Fret numbers row - properly aligned
                fret_num_row = len(card.fretboard)
                
                # String label area (empty)
                ttk.Label(diagram_frame, text="", font=("Arial", 7), width=2).grid(row=fret_num_row, column=0)
                
                # Fret 0 number
                ttk.Label(diagram_frame, text="0", font=("Arial", 7), width=cell_width).grid(row=fret_num_row, column=1)
                
                # Separator for fret numbers
                ttk.Label(diagram_frame, text="|", font=("Arial", 7), width=1).grid(row=fret_num_row, column=2)
                
                # Frets 1-5 numbers
                for col_index in range(1, FRETS + 1):
                    ttk.Label(diagram_frame, text=str(col_index), font=("Arial", 7), width=cell_width).grid(
                        row=fret_num_row, column=col_index + 2)
            
            except Exception as e:
                # In case of error with a specific card, show an error message but continue with other cards
                error_frame = ttk.LabelFrame(self.cards_container, text=f"Error displaying chord: {card.chord.symbol}")
                error_frame.pack(fill=tk.X, padx=10, pady=5)
                ttk.Label(error_frame, text=f"Error: {str(e)}", foreground="red").pack(padx=10, pady=5)
                continue
    
    def _get_marker_text(self, note_type, note_name, mode):
        """Get display text for a note based on display mode"""
        if mode == DisplayMode.STANDARD:
            if note_type == NoteType.BASS_NOTE:
                return "B"
            elif note_type == NoteType.CHORD_NOTE:
                return "X"
            return "."
        else:  # Educational mode
            if note_type == NoteType.NOT_IN_CHORD:
                return "."
            return note_name
    
    def _apply_marker_style(self, label, note_type, mode):
        """Apply visual style based on note type and display mode"""
        if mode == DisplayMode.STANDARD:
            if note_type == NoteType.BASS_NOTE:
                label.configure(background="#ff7675", foreground="white")  # Red background for bass notes
            elif note_type == NoteType.CHORD_NOTE:
                label.configure(background="#74b9ff", foreground="white")  # Blue background for chord notes
        else:  # Educational mode
            if note_type == NoteType.BASS_NOTE:
                label.configure(background="#ff7675", foreground="white", font=("Arial", 9, "bold"))
            elif note_type == NoteType.CHORD_NOTE:
                label.configure(background="#74b9ff", foreground="white", font=("Arial", 9, "bold"))
            # No special styling for non-chord notes in educational mode
    
    def save_cards(self):
        if not self.cards:
            messagebox.showinfo("Info", "No cards to save. Analyze chords first.")
            return
        
        file_path = filedialog.asksaveasfilename(
            title="Save Bass Cards",
            defaultextension=".yaml",
            filetypes=[("YAML files", "*.yaml"), ("All files", "*.*")]
        )
        if not file_path:
            return
        
        try:
            # Prepare data for YAML
            data = {
                'song': {
                    'title': self.song.title,
                    'author': self.song.author,
                    'key': self.song.key
                },
                'settings': {
                    'string_count': self.string_count.get(),
                    'display_mode': self.display_mode.get()
                },
                'chords': [
                    {
                        'symbol': card.chord.symbol,
                        'section': card.chord.section,
                        'bass_note': card.chord.bass_note
                    } for card in self.cards
                ]
            }
            
            with open(file_path, 'w', encoding='utf-8') as file:
                yaml.dump(data, file, allow_unicode=True, sort_keys=False)
            
            messagebox.showinfo("Success", f"Bass cards saved to {file_path}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save cards: {str(e)}")
    
    def load_cards(self):
        file_path = filedialog.askopenfilename(
            title="Load Bass Cards",
            filetypes=[("YAML files", "*.yaml"), ("All files", "*.*")]
        )
        if not file_path:
            return
        
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                data = yaml.safe_load(file)
            
            # Load song metadata
            song_data = data.get('song', {})
            self.song.title = song_data.get('title', '')
            self.song.author = song_data.get('author', '')
            self.song.key = song_data.get('key', '')
            self.title_var.set(self.song.title)
            self.author_var.set(self.song.author)
            
            # Load settings
            settings = data.get('settings', {})
            self.string_count.set(settings.get('string_count', StringCount.FOUR_STRINGS.value))
            self.display_mode.set(settings.get('display_mode', DisplayMode.STANDARD.value))
            
            # Load chords
            self.song.chords = []
            for chord_data in data.get('chords', []):
                chord = Chord(chord_data['symbol'], chord_data['section'])
                chord.bass_note = chord_data['bass_note']
                self.song.chords.append(chord)
            
            # Generate cards
            self.cards = [
                BassCard(chord, self.song.key, self.string_count.get()) 
                for chord in self.song.chords
            ]
            self.display_cards()
            
            messagebox.showinfo("Success", f"Bass cards loaded from {file_path}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load cards: {str(e)}")
    
    def export_html(self):
        if not self.cards:
            messagebox.showinfo("Info", "No cards to export. Analyze chords first.")
            return
        
        file_path = filedialog.asksaveasfilename(
            title="Export to HTML",
            defaultextension=".html",
            filetypes=[("HTML files", "*.html"), ("All files", "*.*")]
        )
        if not file_path:
            return
        
        try:
            with open(file_path, 'w', encoding='utf-8') as file:
                # Write HTML content
                file.write(self.generate_html_content(
                    columns=self.columns_for_export.get(),
                    display_mode=DisplayMode(self.display_mode.get()),
                    string_count=self.string_count.get()
                ))
            
            messagebox.showinfo("Success", f"HTML export saved to {file_path}")
            # Ask if user wants to open the file
            if messagebox.askyesno("Open File", "Open the HTML file in your browser?"):
                webbrowser.open_new_tab(f'file://{os.path.abspath(file_path)}')
        except Exception as e:
            messagebox.showerror("Error", f"Failed to export HTML: {str(e)}")
    
    def print_cards(self):
        if not self.cards:
            messagebox.showinfo("Info", "No cards to print. Analyze chords first.")
            return
        
        # Create temporary HTML file for printing
        with tempfile.NamedTemporaryFile(delete=False, suffix='.html', mode='w', encoding='utf-8') as tmpfile:
            columns = self.columns_for_export.get()
            tmpfile.write(self.generate_html_content(
                columns=columns, 
                print_mode=True,
                display_mode=DisplayMode(self.display_mode.get()),
                string_count=self.string_count.get()
            ))
            tmp_path = tmpfile.name
        
        # Open in browser for printing
        webbrowser.open_new_tab(f'file://{tmp_path}')
        messagebox.showinfo("Print", f"A browser window has opened with the printable version in {columns} column(s) format. Use your browser's print function to print the cards.")
    
    def generate_html_content(self, columns=1, print_mode=False, display_mode=DisplayMode.STANDARD, string_count=4):
        """Generate HTML content for export or printing"""
        column_width = 100 / columns - 2  # -2 for margins
        
        # Calculate cell width based on display mode
        cell_width = 30
        cell_padding = "0px"
        if display_mode == DisplayMode.EDUCATIONAL:
            cell_width = 40
            cell_padding = "0px 2px"
        
        css = f"""
        <style>
            body {{
                font-family: Arial, sans-serif;
                margin: 20px;
                color: #333;
            }}
            .song-meta {{
                background-color: #f0f0f0;
                padding: 15px;
                border-radius: 8px;
                margin-bottom: 20px;
            }}
            .cards-container {{
                display: flex;
                flex-wrap: wrap;
                gap: 20px;
            }}
            .card {{
                border: 1px solid #ccc;
                border-radius: 8px;
                padding: 15px;
                margin-bottom: 20px;
                background-color: #fff;
                box-shadow: 0 2px 5px rgba(0,0,0,0.1);
                flex: 1;
                min-width: {column_width}%;
                box-sizing: border-box;
            }}
            .card-title {{
                font-size: 18px;
                font-weight: bold;
                color: #2c3e50;
                margin-bottom: 10px;
            }}
            .card-details {{
                display: flex;
                flex-wrap: wrap;
                gap: 20px;
                margin-bottom: 15px;
            }}
            .detail-item {{
                min-width: 150px;
            }}
            .detail-label {{
                font-weight: bold;
                color: #3498db;
            }}
            .fretboard {{
                margin-top: 15px;
                font-family: monospace;
            }}
            .string-row {{
                display: flex;
                align-items: center;
                margin-bottom: 2px;
            }}
            .string-label {{
                font-weight: bold;
                width: 25px;
                text-align: center;
                margin-right: 5px;
            }}
            .fret-cell {{
                display: inline-block;
                width: {cell_width}px;
                height: 25px;
                text-align: center;
                line-height: 25px;
                border: 1px solid #999;
                margin: 1px;
                font-weight: bold;
                padding: {cell_padding};
            }}
            .bass-note {{
                background-color: #ff7675;
                color: white;
            }}
            .chord-note {{
                background-color: #74b9ff;
                color: white;
            }}
            .open-string {{
                border-right: 2px solid #333;
                margin-right: 5px;
            }}
            .fret-numbers {{
                display: flex;
                align-items: flex-end;
                margin-top: 5px;
                font-size: 10px;
                color: #666;
                height: 20px;
            }}
            .fret-number {{
                width: {cell_width}px;
                text-align: center;
                font-weight: normal;
                padding: {cell_padding};
            }}
            .divider {{
                width: 15px;
                text-align: center;
                font-weight: bold;
                height: 25px;
                display: flex;
                align-items: center;
                justify-content: center;
            }}
            @media print {{
                body {{
                    margin: 0.5cm;
                }}
                .card {{
                    page-break-inside: avoid;
                    box-shadow: none;
                    border: 1px solid #000;
                }}
                .cards-container {{
                    gap: 5px;
                }}
                @page {{
                    size: A4;
                    margin: 0.5cm;
                }}
            }}
        </style>
        """
        
        if print_mode:
            # Adjust sizes for printing
            cell_height = 22
            cell_font_size = "10px"
            label_font_size = "9px"
            fret_number_font_size = "8px"
            string_label_width = "20px"
            
            if display_mode == DisplayMode.EDUCATIONAL:
                cell_width = 35
            
            css += f"""
            <style>
                .card {{
                    min-width: {column_width}%;
                    padding: 8px;
                    margin: 0 5px 10px 0;
                }}
                .fret-cell {{
                    width: {cell_width}px;
                    height: {cell_height}px;
                    line-height: {cell_height}px;
                    font-size: {cell_font_size};
                    margin: 0;
                    border: 1px solid #666;
                }}
                .string-label {{
                    width: {string_label_width};
                    font-size: {label_font_size};
                }}
                .fret-number {{
                    width: {cell_width}px;
                    font-size: {fret_number_font_size};
                    height: 15px;
                    line-height: 15px;
                }}
                .fret-numbers {{
                    height: 15px;
                    margin-top: 3px;
                }}
                .divider {{
                    height: {cell_height}px;
                    width: 12px;
                    font-size: 10px;
                }}
                .card-title {{
                    font-size: 14px;
                    margin-bottom: 5px;
                }}
                .detail-label {{
                    font-size: 9px;
                }}
                .card-details {{
                    gap: 10px;
                    margin-bottom: 8px;
                }}
            </style>
            """
        
        html = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Bass Chord Cards - {self.song.title}</title>
            {css}
        </head>
        <body>
            <div class="song-meta">
                <h1>{self.song.title}</h1>
                <p><strong>Author:</strong> {self.song.author}</p>
                <p><strong>Key:</strong> {self.song.key}</p>
                <p><strong>Bass Type:</strong> {string_count}-string</p>
            </div>
            <div class="cards-container">
        """
        
        for card in self.cards:
            try:
                # Generate fretboard HTML with visual separation
                fretboard_html = ""
                for string_name, markers in card.fretboard:
                    # Open string cell
                    note_type, note_name = markers[0]
                    open_cell_class = self._get_html_cell_class(note_type)
                    open_cell_text = self._get_html_marker_text(note_type, note_name, display_mode)
                    
                    # Fret cells (1-5)
                    fret_cells = ""
                    for note_type, note_name in markers[1:]:
                        cell_class = self._get_html_cell_class(note_type)
                        cell_text = self._get_html_marker_text(note_type, note_name, display_mode)
                        fret_cells += f'<div class="fret-cell {cell_class}">{cell_text}</div>'
                    
                    fretboard_html += f"""
                    <div class="string-row">
                        <div class="string-label">{string_name}</div>
                        <div class="fret-cell open-string {open_cell_class}">{open_cell_text}</div>
                        <div class="divider">|</div>
                        {fret_cells}
                    </div>
                    """
                
                # Fret numbers (including 0) - properly aligned with cells with bottom padding
                fret_numbers_html = f"""
                <div class="fret-numbers">
                    <div class="string-label"></div>
                    <div class="fret-number">0</div>
                    <div class="divider" style="height:15px">|</div>
                    <div class="fret-number">1</div>
                    <div class="fret-number">2</div>
                    <div class="fret-number">3</div>
                    <div class="fret-number">4</div>
                    <div class="fret-number">5</div>
                </div>
                """
                
                html += f"""
                    <div class="card">
                        <div class="card-title">Chord: {card.chord.symbol} <span style="font-weight:normal">(Section: {card.chord.section})</span></div>
                        <div class="card-details">
                            <div class="detail-item">
                                <div class="detail-label">Scale Degree:</div>
                                <div>{card.scale_degree}</div>
                            </div>
                            <div class="detail-item">
                                <div class="detail-label">Bass Note:</div>
                                <div>{card.chord.bass_note}</div>
                            </div>
                            <div class="detail-item">
                                <div class="detail-label">Chord Notes:</div>
                                <div>{', '.join(card.notes)}</div>
                            </div>
                        </div>
                        <div class="fretboard">
                            {fretboard_html}
                            {fret_numbers_html}
                        </div>
                    </div>
                """
            except Exception as e:
                # In case of error with a specific card, show an error message but continue with other cards
                error_html = f"""
                <div class="card" style="border-color: red;">
                    <div class="card-title" style="color: red;">Error with chord: {card.chord.symbol}</div>
                    <div class="card-details">
                        <div class="detail-item">
                            <div>Error:</div>
                            <div>{str(e)}</div>
                        </div>
                    </div>
                </div>
                """
                html += error_html
                continue
        
        html += """
            </div>
        </body>
        </html>
        """
        return html
    
    def _get_html_cell_class(self, note_type):
        """Get CSS class for HTML cell based on note type"""
        if note_type == NoteType.BASS_NOTE:
            return "bass-note"
        elif note_type == NoteType.CHORD_NOTE:
            return "chord-note"
        return ""
    
    def _get_html_marker_text(self, note_type, note_name, mode):
        """Get display text for HTML cell based on display mode"""
        if mode == DisplayMode.STANDARD:
            if note_type == NoteType.BASS_NOTE:
                return "B"
            elif note_type == NoteType.CHORD_NOTE:
                return "X"
            return "."
        else:  # Educational mode
            if note_type == NoteType.NOT_IN_CHORD:
                return "."
            return note_name

if __name__ == "__main__":
    root = tk.Tk()
    app = BassChordApp(root)
    root.mainloop()