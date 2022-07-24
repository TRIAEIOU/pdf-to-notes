import os, re, subprocess, tempfile, glob, shutil
from aqt import mw
from aqt.qt import *
from aqt.utils import *
from aqt.operations import CollectionOp
from anki import consts, collection

if qtmajor == 6:
    from . import dialog_qt6 as dialog
elif qtmajor == 5:
    from . import dialog_qt5 as dialog

if sys.platform == 'win32' or sys.platform == 'cygwin':
    POPPLER_DIR = os.path.join(os.path.dirname(__file__), "poppler")
    PDFINFO = os.path.join(POPPLER_DIR, "pdfinfo.exe")
    PDFTOHTML = os.path.join(POPPLER_DIR, "pdftohtml.exe")
    PDFTOIMG = os.path.join(POPPLER_DIR, "pdftoppm.exe")
    PDFTOTXT = os.path.join(POPPLER_DIR, "pdftotext.exe")
elif sys.platform == 'linux':
    PDFINFO = "pdfinfo"
    PDFTOHTML = "pdftohtml"
    PDFTOIMG = "pdftoppm"
    PDFTOTXT = "pdftotext"
elif sys.platform == 'darwin':  
    PDFINFO = "pdfinfo"
    PDFTOHTML = "pdftohtml"
    PDFTOIMG = "pdftoppm"
    PDFTOTXT = "pdftotext"

TMP_PGHTML = "pghtml.html"
TMP_PGIMG_PFX = "pgimg"
TMP_PGTXT = "pgtxt.txt"
P2N_TITLE = "Import PDF to notes"
FMT_IMG = "Image"
FMT_HTML = "HTML"
FORMATS = [FMT_IMG, FMT_HTML]
NO_TITLE = "<none>"
SHORTCUT_DEFAULT = "Ctrl+Alt+p"

# CONFIG KEYS
DIR = "Dir"
DECK = "Deck ID"
SUBDECK = "subdeck"
NOTE = "Note type ID"
FRONT = "Front/title field"
BACK = "Back field"
FORMAT = "Page format"
SHORTCUT = "Keyboard shortcut"
FIT_WIDTH = "Fit width"
FIT_HEIGHT = "Fit height"

###########################################################################
# Calculate appropriate scaling from fith/fitw and actual size
###########################################################################
def scale_output(pdf, fitw, fith):
    if fitw or fith:
        info = subprocess.run([PDFINFO, pdf], stdout=subprocess.PIPE, universal_newlines=True, shell=True)
        dimensions = re.search(r'^Page size:\s+([0-9.]+)\s+x\s+([0-9.]+)', info.stdout, flags=re.M)
        pdfw = float(dimensions.group(1))
        pdfh = float(dimensions.group(2))
        if fitw and (not fith or fitw/pdfw <= fith/pdfh):
            scale = fitw/pdfw
        else:
            scale = fith/pdfh
        fit = int(scale * pdfw if pdfw > pdfh else scale * pdfh)
    else:
        scale = None
        fit = None
    return {"scale": scale, "fit": fit}


###########################################################################
# Convert to html, add images to media collection and update html, return list of pages
###########################################################################
def pdf_to_html(pdf, fitw, fith):
    tmp_dir = tempfile.TemporaryDirectory()
    tmp_file = os.path.join(tmp_dir.name, TMP_PGHTML)

    scale = scale_output(pdf, fitw, fith)['scale']
    if not scale:
        scale = 1
    proc_info = subprocess.run([PDFTOHTML, "-c", "-noframes", "-nodrm", "-zoom", str(scale), pdf, tmp_file], stdout=subprocess.PIPE, universal_newlines=True, shell=True)
    with open(tmp_file, encoding='utf-8') as fh:
        html = fh.read()

    def add_html_image(match):
        src = os.path.join(tmp_dir.name, match.group(2))
        dest = mw.col.media.add_file(src)
        return f"{match.group(1)}{dest}{match.group(3)}"
    html = re.sub(r'(<img .*?src=")(.+?)(".*?>)', add_html_image, html, flags=re.M)
    tmp_dir.cleanup()

    pgs_html = re.split(r'^\s*<!--\s*Page\s*\d+\s*-->\s*$', html, flags=re.M)
    pgs_html.pop(0)
    pgs_html[len(pgs_html) - 1] = re.sub(r"(.*?)</body>.*", r"\1", pgs_html[len(pgs_html) - 1], flags=re.S|re.M)
    return pgs_html


###########################################################################
# Convert to text, return list of pages
###########################################################################
def pdf_to_text(pdf):
    tmp_dir = tempfile.TemporaryDirectory()
    tmp_file = os.path.join(tmp_dir.name, TMP_PGTXT)
    proc_info = subprocess.run([PDFTOTXT, "-layout", pdf, tmp_file], stdout=subprocess.PIPE, universal_newlines=True, shell=True)
    with open(tmp_file, encoding='utf-8') as fh:
        file_txt = fh.read()
    tmp_dir.cleanup()
    return file_txt.split('\f')


###########################################################################
# Convert to png, add images to media collection, return list of images (in collection)
###########################################################################
def pdf_to_image(pdf, fitw, fith):
    tmp_dir = tempfile.TemporaryDirectory()
    tmp_file_pfx = os.path.join(tmp_dir.name, TMP_PGIMG_PFX)
    fit = scale_output(pdf, fitw, fith)['fit']
    if fit:
        proc_info = subprocess.run([PDFTOIMG, "-png", "-scale-to", str(fit), pdf, tmp_file_pfx], stdout=subprocess.PIPE, universal_newlines=True, shell=True)
    else:
        proc_info = subprocess.run([PDFTOIMG, "-png", pdf, tmp_file_pfx], stdout=subprocess.PIPE, universal_newlines=True, shell=True)

    match = os.path.join(tmp_dir.name, f"{TMP_PGIMG_PFX}-*.png")
    pgs_img = sorted(glob.glob(match))
    for i, page in enumerate(pgs_img):
        pgs_img[i] = mw.col.media.add_file(page)
    tmp_dir.cleanup()
    return pgs_img


###########################################################################
# Convert PDF to notes according to parameters
###########################################################################
def pdf_to_notes(pdf, fmt, col, deck, note_type_id, front, back, fitw, fith):
    note_type = col.models.get(note_type_id)
    lbl_re = "^.*?$"
    title = os.path.splitext(os.path.basename(pdf))[0]

    pgs_txt = pdf_to_text(pdf)
    if fmt == FMT_HTML:
        pages = pdf_to_html(pdf, fitw, fith)
    elif fmt == FMT_IMG:
        pages = pdf_to_image(pdf, fitw, fith)

    if note_type['type'] == consts.MODEL_CLOZE:
        note = mw.col.new_note(note_type)
        content = ""
        for i, page in enumerate(pages):
            prompt = re.match(lbl_re, pgs_txt[i], flags=re.M|re.S).group(0)
            if fmt == FMT_IMG:
                txt = pgs_txt[i].replace(r'\n', '&#10;').replace(r'"', r'&#34;')
                content += f'{prompt}: {{{{c{str(i + 1)}::<br><img src="{page}" title="{txt}">}}}}<br>'
            else:
                content += f'{prompt}: {{{{c{str(i + 1)}::<br><div class="p2n">{page}</div>}}}}<br>'
        if front != NO_TITLE:
            note[front] = title
        note[back] = content
        changes = mw.col.add_note(note, deck)
    else:
        for i, page in enumerate(pages):
            note = mw.col.new_note(note_type)
            note[front] += re.match(lbl_re, pgs_txt[i], flags=re.M|re.S).group(0)
            if fmt == FMT_IMG:
                txt = pgs_txt[i].replace(r'"', r'\"')
                note[back] += f'<img src="{page}" alt="{txt}">'
            else:
                note[back] += f'<div class="p2n">{page}</div>'
            changes = mw.col.add_note(note, deck)
        changes = collection.OpChanges()

    return changes


###########################################################################
# Main dialog that sets PDF to notes parameters
###########################################################################
class P2N_main_dlg(QDialog):
    ############
    # Attributes
    last_dir = ""
    pdfs = []

    def __init__(self):
        QDialog.__init__(self, mw)
        self.ui = dialog.Ui_dialog()
        self.ui.setupUi(self)
        self.ui.file.clicked.connect(self.select_file)
        self.ui.deck.setFocus()
        self.ui.note.currentTextChanged.connect(self.select_note_type)
        decks = mw.col.decks.all_names_and_ids(skip_empty_default=False, include_filtered=False)
        for deck in decks:
            self.ui.deck.addItem(deck.name, deck.id)
        note_types = mw.col.models.all_names_and_ids()
        for note_type in note_types:
            self.ui.note.addItem(note_type.name, note_type.id)
        for fmt in FORMATS:
            self.ui.format.addItem(fmt)
        self.ui.import_btn.setShortcut(QKeySequence('Ctrl+Return'))

        self.load_config()
        # World's ugliest hack to get a focus box to show around the file button on entry
        self.ui.deck.setFocus()
        QCoreApplication.postEvent(self, QKeyEvent(QEvent.KeyPress, Qt.Key_Tab, Qt.ShiftModifier))
        self.exec()


    ###########################################################################
    # Main dialog accept
    ###########################################################################
    def accept(self):
        def import_pdfs(pdfs, fmt, col, deck, note, front, back, width, height):
            changes = collection.OpChanges()
            for pdf in pdfs:
                if self.ui.subdeck.isChecked():
                    title = f'{col.decks.get(did=deck)["name"]}::{os.path.splitext(os.path.basename(pdf))[0]}'
                    out_deck = col.decks.add_normal_deck_with_name(title).id
                else:
                    out_deck = deck
                changes = pdf_to_notes(pdf, fmt, col, out_deck, note, front, back, width, height)
            return changes

        bgop = CollectionOp(parent=mw, op=lambda col: import_pdfs(self.pdfs, self.ui.format.currentText(), col, self.ui.deck.currentData(), self.ui.note.currentData(), self.ui.front.currentText(), self.ui.back.currentText(), self.ui.width.value(), self.ui.height.value()))
        bgop.run_in_background()
        bgop.success(lambda col: tooltip(msg=f'Import of {", ".join([os.path.basename(pdf) for pdf in self.pdfs])} completed.', parent=mw))
        self.save_config()
        QDialog.accept(self)
        

    ###########################################################################
    # Main dialog reject
    ###########################################################################
    def reject(self):
        self.save_config()
        QDialog.reject(self) 


    ###########################################################################
    # Load configuration from config Dict (from Anki config file normally)
    ###########################################################################
    def load_config(self):
        config = mw.addonManager.getConfig(__name__)
        if config.get(DIR):
            self.last_dir = config[DIR]
        if config.get(DECK):
            i = self.ui.deck.findData(config[DECK], flags=Qt.MatchExactly)
            if i != -1:
                self.ui.deck.setCurrentIndex(i)
        if config.get(SUBDECK):
            i = self.ui.subdeck.setChecked(config[SUBDECK])
        if config.get(NOTE):
            i = self.ui.note.findData(config[NOTE], flags=Qt.MatchExactly)
            if i != -1:
                self.ui.note.setCurrentIndex(i)
        else:
            self.select_note_type()
        if config.get(FRONT):
            i = self.ui.front.findText(config[FRONT])
            if i != -1:
                self.ui.front.setCurrentIndex(i)
        if config.get(BACK):
            i = self.ui.back.findText(config[BACK])
            if i != -1:
                self.ui.back.setCurrentIndex(i)
        if config.get(FORMAT):
            i = self.ui.format.findText(config[FORMAT])
            if i != -1:
                self.ui.format.setCurrentIndex(i)
        if config.get(FIT_WIDTH):
            self.ui.width.setValue(config[FIT_WIDTH])
        if config.get(FIT_HEIGHT):
            self.ui.height.setValue(config[FIT_HEIGHT])


    ###########################################################################
    # Save current configuration to file
    ###########################################################################
    def save_config(self):
        config = {
            DIR: self.last_dir,
            DECK: self.ui.deck.currentData(),
            SUBDECK: self.ui.subdeck.isChecked(),
            NOTE: self.ui.note.currentData(),
            FRONT: self.ui.front.currentText(),
            BACK: self.ui.back.currentText(),
            FORMAT: self.ui.format.currentText(),
            FIT_WIDTH: self.ui.width.value(),
            FIT_HEIGHT: self.ui.height.value()
        }
        mw.addonManager.writeConfig(__name__, config)


    ###########################################################################
    # Ugly hack to route return in a logical manner
    ###########################################################################
    def keyPressEvent(self, event):
        if event.key() ==  Qt.Key_Return:
            fcs = self.focusWidget()
            if type(fcs) is QComboBox:
                fcs.showPopup()
            if type(fcs) is QPushButton:
                fcs.click()
        else:
            QDialog.keyPressEvent(self, event)


    ###########################################################################
    # Button press to open Open File dialog
    ###########################################################################
    def select_file(self):
        fd = QFileDialog(self)
        fd.setWindowTitle("Select PDF")
        fd.setDirectory(self.last_dir)
        fd.setFileMode(QFileDialog.ExistingFiles)
        fd.setNameFilter("PDF files (*.pdf)")
        fde = fd.exec()

        if fde:
            self.pdfs = fd.selectedFiles()
            self.ui.file.setText(f'/'.join([os.path.basename(pdf) for pdf in self.pdfs]))
            self.ui.file.setToolTip(f'\n'.join(self.pdfs))
            self.last_dir = os.path.dirname(self.pdfs[0])
            self.ui.import_btn.setEnabled(True)

    ###########################################################################
    # Set available fields to match selected note type
    ###########################################################################
    def select_note_type(self):
        note_tid = self.ui.note.currentData()
        note = mw.col.models.get(note_tid)
        fields = mw.col.models.field_names(note)
        self.ui.front.clear()
        self.ui.back.clear()
        if note['type'] == consts.MODEL_CLOZE:
            self.ui.front_label.setText("Title field")
            self.ui.back_label.setText("Cloze field")
            self.ui.front.addItem(NO_TITLE)
        else:
            self.ui.front_label.setText("Front")
            self.ui.back_label.setText("Back")
        self.ui.front.addItems(fields)
        self.ui.back.addItems(fields)


###########################################################################
# "Main" code
###########################################################################
# Manage plattforms without included poppler 
missing = []
if not (sys.platform == 'win32' or sys.platform == 'cygwin'):
    if not shutil.which(PDFINFO):
        missing.append(PDFINFO)
    if not shutil.which(PDFTOHTML):
        missing.append(PDFTOHTML)
    if not shutil.which(PDFTOIMG):
        missing.append(PDFTOIMG)
    if not shutil.which(PDFTOTXT):
        missing.append(PDFTOTXT)
    if missing:
        if sys.platform == 'darwin':
            instr = 'with homebrew (brew.sh) "brew install poppler-utils" or equivalent'
        else:
            instr = '"sudo apt install poppler-utils" or equivalent'
        showWarning(text=f"""<p>PDF to notes depends on the poppler library (https://poppler.freedesktop.org), specifically the following parts:</p><ul><li>{PDFINFO}</li><li>{PDFTOHTML}</li><li>{PDFTOIMG}</li><li>{PDFTOTXT}</li></ul>The following parts were not detected on the system:<ul><li>{'</li><li>'.join(missing)}</li></ul><p>The poppler library cannot be included with the addon on this plattform. please install the poppler library through a package manager ({instr}) and ensure the above are in the path.</p>""", parent=mw, title="PDF to notes", textFormat="rich")


action = QAction(P2N_TITLE, mw)
config = mw.addonManager.getConfig(__name__)
if config.get(SHORTCUT):
    action.setShortcut(QKeySequence(config[SHORTCUT]))
else:
    action.setShortcut(QKeySequence(config[SHORTCUT_DEFAULT]))
action.triggered.connect(lambda: P2N_main_dlg())
if missing:
    action.setEnabled(False)
mw.form.menuTools.addAction(action)
