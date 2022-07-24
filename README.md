# PDF to notes
Using the poppler library (https://poppler.freedesktop.org/) the add-on converts a PDF file into notes.
- Question/prompt extracted from each page (the first line of text)
- Convert PDF pages to separate "normal" (front/back) notes or separate clozes in a single cloze type note.
- PDF pages inserted as images or HTML (using poppler pdftoppm and pdftohtml).

<img src="https://github.com/TRIAEIOU/PDF-to-notes/blob/main/Screenshots/launch.jpg?raw=true" height="200">
<img src="https://github.com/TRIAEIOU/PDF-to-notes/blob/main/Screenshots/dialog.jpg?raw=true" height="200">
<img src="https://github.com/TRIAEIOU/PDF-to-notes/blob/main/Screenshots/note.jpg?raw=true" height="200">

- PDF file (can be multiple): select file(s) to convert.
- Deck: Which deck the added note(s) will be inserted into.
- Note type: Which note type to use for insertion, supports "normal" (front/back) note types as well as cloze note types.
- Subdeck: If checked a subdeck (with the PDF file name as title) will be created for each file. Note that if note type is a cloze style note there will be one subdeck for each note.
- Front ("normal" (front/back) note type): Which field to insert the "question" (first line of text in the page) in.
- Back ("normal" (front/back) note type): Which field to insert the "answer" in.
- Title field (cloze note type): Which field to insert PDF file name as title (for note types, such as the built-in cloze, that do not have a suitable field for this, select <none>).
- Cloze field (cloze note type): Which field to insert clozes into. Clozes are inserted as prompt: {{c1::<br>answer}}<br> where prompt is the first line of text extracted from the page and answer is either an image of the page or a <div> with the page HTML.
- Format: Format to insert the pages in, either as images (will preserve exact layout and work well on all screen sizes but no editable/selectable text) or HTML (does not give perfect results on any screen, especially not small screens but text can be copied/edited).
- Configurable keyboard shortcut (default Ctrl+Alt+P) to open dialog from main window
- Fit width/height: output will be scaled proportionally to fit inside the specified box (0 means not constraint in that direction, i.e. 0 x 0 means no scaling and 600 x 0 means output will be 600 px wide and height scaled proportionally).
- Return will select the current item (same as space) whereas Ctrl+Return will start the import and Escape will cancel the dialog.
- https://github.com/TRIAEIOU/PDF-to-notes

## Installation
- Windows binaries of poppler are packaged in the addon (https://github.com/oschwartz10612/poppler-windows).
- On many Linux installations it is included in the default install, otherwise install with a package manger, for instance apt: `sudo apt install poppler-utils`.
- On macOS it can be installed with the homebrew package manager: `brew install poppler` (untested as I don't have access to a Mac).

## Changelog
- 2022-01-01: Prepare code for Anki Qt5 to Qt6 transition.
- 2022-01-31: Add keyboard shortcut to open dialog from main window. Add option to scale output. Make keyboard input more intuitive. Allow multiple PDF file selection.
- 2022-02-06: Bug fix on PDF to image and no scaling.
- 2022-02-11: Added option to create subdeck for each PDF file.
- 2022-05-13: Fixed shortcut bug.
- 2022-05-18: Bug fixes.