# FOLIO New Materials

A small program that connects to your FOLIO library system every night,
finds the books, DVDs, and other items that arrived that day, and produces
a webpage your patrons can browse. The page shows the cover image, title,
author, call number, and a link back to your discovery service (EDS).

You do not need to be a programmer to set this up, but you do need to
follow the instructions carefully. The total setup time, the first time,
is usually about thirty minutes.

## Live demo

A working preview of the page is hosted at
**https://smithcollegelibraries.github.io/folio-new-material/**

The demo uses entirely synthetic data — no real library collection is
represented. Browse the demo to see how the filter, sort, view-toggle,
and subject-grouping features behave before deciding whether to install.

---

## Table of contents

1. [What you get when this is running](#what-you-get-when-this-is-running)
2. [What you will need before you start](#what-you-will-need-before-you-start)
3. [Step 1. Install Python on your computer](#step-1-install-python-on-your-computer)
4. [Step 2. Download this software](#step-2-download-this-software)
5. [Step 3. Install the supporting Python libraries](#step-3-install-the-supporting-python-libraries)
6. [Step 4. Create your settings file](#step-4-create-your-settings-file)
7. [Step 5. Fill in the settings](#step-5-fill-in-the-settings)
8. [Step 6. Run it once to test](#step-6-run-it-once-to-test)
9. [Step 7. Schedule it to run automatically each night](#step-7-schedule-it-to-run-automatically-each-night)
10. [Step 8. Publish the page so patrons can see it](#step-8-publish-the-page-so-patrons-can-see-it)
11. [Updating the software later](#updating-the-software-later)
12. [Troubleshooting](#troubleshooting)
13. [Files this program writes](#files-this-program-writes)
14. [Customising what your patrons see](#customising-what-your-patrons-see)
15. [Keeping credentials safe](#keeping-credentials-safe)
16. [Glossary](#glossary)
17. [Reporting problems and contributing](#reporting-problems-and-contributing)
18. [License](#license)

---

## What you get when this is running

Every morning, this program produces an accessible HTML page that lists
the materials your library received in the last 30 days (or whatever
window you configure). The page includes:

- A header with your library's logo, name, and brand colors
- A search box for filtering by title or author
- A dropdown to filter by material type (Books, DVDs, Music CDs, etc.)
- A dropdown for subject area (Engineering, Sciences, Humanities, etc.)
- Sort options (newest first, alphabetical)
- A toggle between a visual grid view and a compact table view
- One card per item with cover image, title, author, year, call number,
  location, and status

Patrons click any title to jump straight to the catalog record in EDS.

The output is a small static website (one HTML file plus a few support
files). You can email it, copy it to a USB stick, post it to your library's
web server, or just open it directly from your computer. No special
hosting or database is required.

---

## What you will need before you start

Before beginning, please make sure you have all of the following:

### Required

- **A computer.** Mac, Windows, or Linux. This program runs on all three.
- **An internet connection.** The program talks to FOLIO and (optionally)
  some other services over the internet.
- **A FOLIO account with read permissions for Orders and Inventory.** Ask
  your FOLIO administrator if you are not sure. The user account needs
  to be able to read order lines and instance records.
- **Your FOLIO Okapi gateway URL.** This is the base address of your
  FOLIO system's API, such as `https://api-fivecolleges.folio.ebsco.com`.
  Your FOLIO administrator can provide this.
- **Your FOLIO tenant ID.** A short code that identifies your library
  inside FOLIO, such as `fs00001006`.

### Helpful (but not required)

- **A FOLIO Edge API key.** If your institution uses the FOLIO Edge
  service (most FOLIO sites do), this lets the program fetch live
  shelf-status data and consortium-wide holdings. Without it the program
  still works, but the call numbers and locations come from a slightly
  less rich source.
- **An EDS database ID and access-number prefix.** These let the page
  link each title to your discovery service. If you do not have these
  yet, the page still shows everything else; the titles just are not
  clickable links.
- **A TMDB API key.** Free from https://www.themoviedb.org. Adds cover
  posters for DVDs and other video recordings. Books work without it.
- **A web server, shared drive, or file server.** If you want patrons to
  view the page, you will need somewhere to put the files. A static
  hosting setup (the simplest kind) is sufficient.

---

## Step 1. Install Python on your computer

This program is written in Python, so you need Python installed. Version
3.9 or newer is required.

### On a Mac

Recent versions of macOS come with Python preinstalled, but it is often
slightly old. To check what you have, open the Terminal application
(press Command-Space, type "Terminal", press Return) and type:

```
python3 --version
```

If the version shown is 3.9 or higher, you are ready. If it is older,
or you get an error, install Python from https://www.python.org/downloads/
by clicking the yellow "Download Python" button on the homepage. Run the
installer and accept the defaults.

### On Windows

Go to https://www.python.org/downloads/ and click the yellow
"Download Python" button. Run the installer. **Important:** on the
first screen of the installer, tick the box that says "Add Python to PATH"
before clicking Install Now. If you skip this, later steps will fail with
a "command not found" message.

When the installer finishes, open Command Prompt (press the Windows key,
type "cmd", press Enter) and type:

```
python --version
```

You should see something like `Python 3.12.1`.

### On Linux

Most Linux distributions ship Python by default. Open a terminal and run:

```
python3 --version
```

If the version is older than 3.9, install a newer one using your
distribution's package manager. For Ubuntu or Debian:

```
sudo apt update
sudo apt install python3 python3-pip
```

---

## Step 2. Download this software

You have two ways to do this. Either works.

### Option A. Download as a ZIP file (no Git required)

1. On the GitHub page for this project, click the green "Code" button.
2. Choose "Download ZIP".
3. Save the ZIP file somewhere you will remember, such as your Documents
   folder.
4. Double-click the ZIP file to unpack it. You will end up with a folder
   named something like `folio-new-books-main`.
5. Rename the folder to just `folio-new-books` if you would like a tidier
   name.

### Option B. Use Git (recommended if you plan to update later)

If you already have Git installed, open a terminal and run:

```
git clone https://github.com/YOUR-ORG/folio-new-books.git
```

Replace `YOUR-ORG` with the actual GitHub organisation or username that
hosts the code. This creates a folder named `folio-new-books` in your
current directory.

Throughout the rest of these instructions, when we say "the project
folder", we mean this folder.

---

## Step 3. Install the supporting Python libraries

The program uses a few small libraries that need to be installed
separately. From within the project folder, open a terminal and run:

On macOS or Linux:

```
pip3 install -r requirements.txt
```

On Windows:

```
pip install -r requirements.txt
```

You will see a list of packages being downloaded and installed. The whole
process takes about a minute. If you see no error at the end, you are
done with this step.

### If you see permission errors

If pip complains about not having permission to install, try adding
`--user` to the command:

```
pip3 install --user -r requirements.txt
```

This installs the libraries into your own home directory, which always
works even on shared machines.

---

## Step 4. Create your settings file

The program needs to know things like your FOLIO username and password,
your library's branding, and other preferences. These all live in a file
called `config.ini`.

We provide a template called `config.ini.example` that you should copy
and then fill in.

From inside the project folder, run:

On macOS or Linux:

```
cp config.ini.example config.ini
```

On Windows:

```
copy config.ini.example config.ini
```

This creates your live settings file. You now have two similar files:

- `config.ini.example` — the template, kept for reference. Do not edit this.
- `config.ini` — your actual settings, with your real passwords. Edit this.

**Important.** The file `config.ini` contains your FOLIO password and
other secrets. It is set up to be ignored by Git so it never accidentally
ends up in a public repository. Never email it, post it on a help forum,
or share it without removing the passwords first.

---

## Step 5. Fill in the settings

Open `config.ini` in any text editor. On Mac, TextEdit works (but make
sure to use "Format → Make Plain Text" first). On Windows, Notepad works
fine. Programmers often use VS Code or Notepad++, but anything that saves
plain text is acceptable.

The settings file is organised into sections, each starting with a name
in square brackets like `[folio]`. Here is what each section does and
which values you must change.

### [folio] section — connecting to your FOLIO system

```
[folio]
base_url = https://api-fivecolleges.folio.ebsco.com
tenant = fs00001006
username = your_username
password = your_password
edge_api =
edge_api_key =
```

| Setting | What to put here |
|---------|------------------|
| `base_url` | The Okapi gateway URL from your FOLIO administrator. No trailing slash. |
| `tenant` | Your FOLIO tenant ID, also from your administrator. |
| `username` | The FOLIO user account this program will log in as. |
| `password` | That account's password. |
| `edge_api` | Optional. The base URL for FOLIO Edge if your institution uses it (e.g. `https://edge-fivecolleges.folio.ebsco.com`). |
| `edge_api_key` | Optional. The API key that goes with `edge_api`. |

If you do not have Edge API access, leave `edge_api` and `edge_api_key`
blank. The program will still work; it just gets call numbers and
locations from a slightly less complete source.

### [eds] section — links to your discovery service

```
[eds]
db_id = 4e4lys
catalog_db = cat09206a
an_prefix = scf.oai.edge.fivecolleges.folio.ebsco.com.fs00001006
an_separator = dots
link_strategy = openurl
```

These values let the program build a clickable link from each title back
to the catalog record in EDS. If you do not know what to put here, skip
this section (leave the values blank or as placeholders) — the page will
still render, but titles will not be clickable.

| Setting | What to put here |
|---------|------------------|
| `db_id` | The short code in EDS URLs after `/c/`, such as `4e4lys`. Look at any EDS permalink you have to find it. |
| `catalog_db` | The catalog database identifier, such as `cat09206a`. Visible in EDS record URLs. |
| `an_prefix` | The unique identifier prefix for your FOLIO records inside EDS. For Five Colleges this is `scf.oai.edge.fivecolleges.folio.ebsco.com.fs00001006`. Your EDS account manager can confirm. |
| `an_separator` | `dots` or `dashes`, depending on how your records are stored in EDS. Try `dots` first. |
| `link_strategy` | `openurl` (recommended) or `search`. `openurl` produces a direct link to the record. `search` produces a search-results link that always works even for very new records. |

**Very important.** If `an_prefix` still contains the word `example` from
the template (`scf.oai.edge.example.folio.ebsco.com.fs00001006`), every
link will go to an EDS "not found" page. The program will print a warning
about this in its log when you run it, so watch for that.

### [google] section — cover images for books

```
[google]
enabled = true
```

This controls whether the program tries to fetch cover images from Google
Books. It is free and requires no API key. Set to `false` if you would
prefer no covers (the page will use a coloured placeholder with the title
written on it).

### [tmdb] section — cover posters for DVDs

```
[tmdb]
api_key =
poster_size = w500
```

Get a free API key at https://www.themoviedb.org/settings/api. Paste it
into `api_key`. Without an API key, DVDs use placeholders. Books do not
need TMDB.

### [output] section — appearance and behaviour

```
[output]
days = 30
output_file = output/new-materials.html
title = New Materials
institution_name = Your Library
logo_url =
primary_color = #003366
accent_color = #ffffff
default_view = grid
holdings_display = summary
pages_per_type = false
log_file = logs/folio-new-books.log
```

| Setting | What to put here |
|---------|------------------|
| `days` | How many days back to look for new materials. |
| `output_file` | Where to save the generated HTML page. Relative paths are relative to the folder you ran the program from. |
| `title` | The page heading shown to patrons. |
| `institution_name` | Your library's name, shown in the header and footer. |
| `logo_url` | A URL to your library's logo image. Leave blank for no logo. |
| `primary_color` | Header background color, as a hex code. |
| `accent_color` | Text color on the primary background. |
| `default_view` | `grid` or `table`. Patrons can still toggle between the two; this just sets which one shows first. |
| `holdings_display` | `none`, `compact`, `summary`, or `detailed`. Controls how much copy-availability information shows on each card. `summary` is the right choice for most libraries. |
| `pages_per_type` | If `true`, the program writes a separate page per material type (e.g. `new-books.html`, `new-dvds.html`) instead of one combined page. |
| `log_file` | Where to write the runtime log file. Set to `none` to disable file logging. |

### [material_types] section — which formats to include

```
[material_types]
# Leave this empty to include all material types from FOLIO.
# To restrict, list specific UUIDs:
# 2d72aa13-2451-41fe-afc7-b3dc7c131389 = Books
# faa0cd0a-e408-4b57-acff-1c3f9171723d = DVD
```

If you leave this section empty (or omit it entirely), the program
fetches every material type from FOLIO and presents them all. This is
the simplest configuration and what most libraries should use.

If you only want certain formats (for example, books and DVDs but not
e-resources), you can list their FOLIO UUIDs and display labels here.
Your FOLIO administrator can find the UUIDs in the FOLIO Settings
application under Inventory → Material types.

### [subject_groups] section — grouping by subject area

```
[subject_groups]
lcc_grouping = true
```

When `lcc_grouping = true`, the program reads each item's call number
and groups it by Library of Congress Classification. Items end up sorted
into roughly 150 subject areas (Mathematics; Computer Science, Astronomy,
English Literature, and so on). A second dropdown labelled "Subject area"
appears in the page toolbar.

This works well for any library that uses LCC. If you use Dewey or
another scheme, leave `lcc_grouping = false` or provide your own keyword
groups. See `config.ini.example` for the full options.

---

## Step 6. Run it once to test

You are now ready to test. Open a terminal, navigate to the project
folder, and run:

On macOS or Linux:

```
python3 generate.py --verbose
```

On Windows:

```
python generate.py --verbose
```

You should see output similar to this:

```
2026-05-14 06:00:00  INFO  __main__  ──────────────────────────────────
2026-05-14 06:00:00  INFO  __main__  FOLIO New Materials — run starting
2026-05-14 06:00:00  INFO  __main__  Config: config.ini
2026-05-14 06:00:01  INFO  __main__  Date range: 2026-04-14 → 2026-05-14
2026-05-14 06:00:02  INFO  __main__  FOLIO authentication successful
2026-05-14 06:00:05  INFO  __main__  Retrieved 42 order lines
2026-05-14 06:00:09  INFO  __main__  Fetched details for 38 instances
2026-05-14 06:00:11  INFO  __main__  Fetching cover images for 38 items
2026-05-14 06:00:25  INFO  __main__  HTML written to output/new-materials.html
2026-05-14 06:00:25  INFO  __main__  Done — 38 items written to output/new-materials.html
```

If you see this kind of output, the program is working. Open the file it
mentions (`output/new-materials.html`) in any web browser to see your
new-materials page. Double-clicking the file in your file manager should
open it.

If you see errors instead, skip to the [Troubleshooting](#troubleshooting)
section.

---

## Step 7. Schedule it to run automatically each night

For your patrons to see fresh listings each morning, the program needs to
run automatically once a day. Most libraries schedule it to run very
early in the morning, before the library opens.

### On macOS or Linux (using cron)

Open a terminal and run:

```
crontab -e
```

This opens your personal cron schedule in a text editor. Add a line like
this at the bottom (use Tab to navigate if the editor is vi):

```
0 5 * * * cd /full/path/to/folio-new-books && /usr/bin/python3 generate.py
```

The five fields at the start are: minute, hour, day of month, month, day
of week. `0 5 * * *` means "every day at 5:00 AM". Adjust the path to
match where you installed the project.

To confirm cron will run your script, you can also schedule it to run a
minute from now temporarily, watch the log file, then change it back.

### On Windows (using Task Scheduler)

1. Open Task Scheduler from the Start menu.
2. Click "Create Basic Task" on the right.
3. Give it a name like "FOLIO New Materials".
4. Choose "Daily" and a time before opening (5:00 AM is common).
5. For "Action", choose "Start a program".
6. For "Program/script", browse to your Python executable (often
   `C:\Python312\python.exe` or similar). Run `where python` in a
   Command Prompt if you are not sure.
7. For "Add arguments", put `generate.py`.
8. For "Start in", put the full path to the project folder.

After saving, you can right-click the task and choose "Run" to test it
immediately.

---

## Step 8. Publish the page so patrons can see it

You have several options here. Pick whichever suits your library's
existing setup.

### Option A. Copy the output to your existing web server

This is the most common setup. The program writes a folder structure
like this:

```
output/
  new-materials.html
  assets/
    styles.css
    app.js
    lcc-classes.json
    lcc-subjects.json
  data/
    items.json
```

Copy the entire `output` folder (or its contents) to a folder on your
web server that is served via HTTP. The page is a complete static site,
so any web hosting will work — no database, no server-side scripting.

To do this automatically each night, change the cron command to write
the output directly to your web server's directory:

```
0 5 * * * cd /opt/folio-new-books && /usr/bin/python3 generate.py \
    --output /var/www/library/new-materials/new-materials.html
```

The `assets/` and `data/` folders are created automatically next to the
HTML file.

### Option B. Host on a free static-site service

Services like Netlify, GitHub Pages, or your campus's static-hosting
service can serve the output. Configure them to look at your `output/`
folder.

### Option C. Open it locally

If only library staff need to see it, you can just open
`output/new-materials.html` directly in a web browser whenever you want
to check what came in. No hosting needed.

---

## Updating the software later

If you downloaded the ZIP, download a fresh ZIP and replace the project
folder. Your `config.ini` lives outside the ZIP, so it will not be
overwritten as long as you keep a backup.

If you used Git, run this in the project folder:

```
git pull
```

After updating, re-run the dependency install in case anything new is
needed:

```
pip3 install -r requirements.txt
```

---

## Troubleshooting

### Configuration error: Missing required config

The program prints `Missing required config: [section] key` when a value
you must provide is blank or missing. Open `config.ini` and fill in the
named field. The three required fields are
`[folio] base_url`, `[folio] username`, and `[folio] password`.

### FOLIO authentication failed

Either your username or password is wrong, or the `base_url` and `tenant`
do not match. Double-check all four values. Note that FOLIO is
case-sensitive — `MyTenant` and `mytenant` are not the same.

If you suspect your account is locked, try logging into the FOLIO web
interface with the same credentials.

### Every EDS link goes to "not_found"

Almost certainly your `an_prefix` setting still has the word `example`
in it. Replace `example` with your institution's actual identifier
(your EDS account manager can confirm — for Five Colleges it is
`fivecolleges`). Re-run the program; the links should resolve to real
records the next day.

This is so common that the program prints a warning about it at startup.
Look for "appears to contain the placeholder" in your log file.

### Empty page / "No new materials in this date range"

This means the program ran successfully but found no items received in
the last 30 days (or whatever window you set). Possibilities:

- Your `days` setting is too short — try `90` to see if older items appear.
- Your account does not have read access to Orders in FOLIO. Ask your
  administrator.
- No items have receipt status "Fully Received" yet. The program only
  shows received items, not items merely on order.

### Cover images are not appearing

Books should get cover images automatically from Google Books, which is
free. If you see colored placeholders instead:

- Check that `enabled = true` is set in the `[google]` section.
- Confirm your computer or server has internet access (the program calls
  `books.google.com` and similar).
- Not every book has a cover image available in Google Books. Older
  books, foreign-language titles, and items without ISBNs sometimes do
  not.

For DVDs, you need a TMDB API key. See [Step 5](#step-5-fill-in-the-settings).

### "Permission denied" when running pip or python

On a shared computer, you may need to install Python libraries into your
own user directory rather than system-wide:

```
pip3 install --user -r requirements.txt
```

### The cron job runs but nothing changes on the website

Check that the cron job is writing the output to the same folder your
web server is serving from. The `--output` flag in the cron command must
point to the right place. The log file (`logs/folio-new-books.log` by
default) will tell you where the program actually wrote.

If you are not sure where cron is running, add this to the top of your
cron command for a one-off test:

```
0 5 * * * cd /opt/folio-new-books && pwd > /tmp/cron-test.txt && python3 generate.py
```

Then look at `/tmp/cron-test.txt` after the cron runs.

---

## Files this program writes

After a successful run, you will find these files:

```
output/
  new-materials.html        - the main page patrons will view
  assets/
    styles.css              - styling for the page
    app.js                  - filtering, sorting, view-toggle behaviour
    lcc-classes.json        - LCC class lookup table (editable)
    lcc-subjects.json       - subject keyword lookup table (editable)
  data/
    items.json              - the same data in machine-readable form
logs/
  folio-new-books.log       - the run log
```

The two JSON files under `data/` are useful if you want to pipe the
new-materials data into another system (an RSS feed generator, a campus
portal, a dashboard, etc.). They are well-formed JSON and stable across
releases.

The log file under `logs/` rotates automatically: when it reaches 10 MB
it is renamed and a new one started. Up to five backup files are kept.

---

## Customising what your patrons see

### Brand colors and logo

Change `primary_color`, `accent_color`, `logo_url`, and `institution_name`
in the `[output]` section of `config.ini`. No code changes needed.

### The list of subject areas

The file `static/lcc-subjects.json` maps subject keywords like
"philosophy" or "computer programming" to LCC class letters. If you find
yourself wishing a particular subject was classified differently, edit
this file and add your own entries.

Likewise, `static/lcc-classes.json` controls the human-readable label
shown for each LCC class. You can rename "Mathematics; Computer Science"
to just "Mathematics" if your library prefers shorter labels.

After editing either file, re-run the program; changes take effect on
the next page generation.

### Removing the format dropdown

If your library only stocks one or two formats, the format dropdown is
shown automatically when more than one format appears in the results. To
hide it entirely, you can restrict the listing to a single material type
in the `[material_types]` section.

---

## Keeping credentials safe

Your `config.ini` file contains your FOLIO password and possibly other
API keys. To keep them safe:

- The `.gitignore` file in this project is configured to exclude
  `config.ini`, so it cannot accidentally end up in version control.
- If you need to ask for help, post the contents of
  `config.ini.example` (which has only placeholders) and never the live
  `config.ini`. Or, if you must share a redacted version, replace all
  passwords and API keys with the word `REDACTED` before sending.
- The program should be run from outside any web-server document root,
  so that `config.ini` is never accidentally served as a static file.
  In other words, install it under `/opt/folio-new-books` or in your
  home directory, never under `/var/www`.
- If you suspect your FOLIO password may have leaked, change it in
  FOLIO immediately and update `config.ini`.

---

## Glossary

**FOLIO** — The library services platform used to manage acquisitions,
inventory, circulation, and so on. This program reads from it.

**Okapi** — The FOLIO API gateway. The `base_url` in your configuration
points to this.

**mod-search** — A FOLIO module that provides searchable bibliographic
data. The program queries this for instance details and subjects.

**RTAC** — Real-Time Availability Check. A FOLIO Edge endpoint that
returns up-to-the-minute holdings and availability data for an instance.
Used when an Edge API key is configured.

**Edge API** — A simpler, apikey-authenticated FOLIO API designed for
external consumers (discovery services, link resolvers, etc.). Separate
from Okapi.

**EDS** — EBSCO Discovery Service. The patron-facing search interface
that the page links to.

**OpenURL** — A standard format for "find me this record" web addresses,
used by EDS and similar services.

**Access number (AN)** — The unique identifier EDS uses to find a record
in its index. The `an_prefix` in your configuration is the portion of
the AN that identifies your institution.

**LCC** — Library of Congress Classification. The call-number scheme
most US academic libraries use (call numbers starting with letters like
PR, QA, HV). The program groups items by LCC class when enabled.

**Dewey** — Dewey Decimal Classification, an alternative call-number
scheme used by many public libraries (call numbers starting with
numbers like 641.5). The LCC grouping feature does not classify Dewey
numbers; if your library uses Dewey, you can leave LCC grouping off or
provide your own keyword-based groups.

**Material type** — In FOLIO, the format category of an item (Book, DVD,
Music CD, Periodical, etc.). Each has a UUID.

**ISBN** — International Standard Book Number. A 10- or 13-digit
identifier most books have.

**OCLC number** — A worldwide bibliographic identifier assigned by OCLC
(formerly the Online Computer Library Center). Useful for items without
ISBNs.

**Cron** — The Unix/Linux/macOS facility for scheduling a command to run
automatically on a schedule.

**Task Scheduler** — The Windows equivalent of cron.

---

## Regenerating the public demo

The demo hosted on GitHub Pages is generated from `tools/generate_demo.py`,
which feeds invented data through the real generator. To refresh the demo
(after a UI change, for example):

```
python3 tools/generate_demo.py
git add docs/
git commit -m "Refresh GitHub Pages demo"
git push
```

GitHub Pages serves the contents of the `docs/` folder on the `main`
branch. To enable Pages on a fresh fork, go to Settings → Pages, choose
"Deploy from a branch", and select `main` / `docs`.

The `.nojekyll` file in `docs/` disables Jekyll processing, which would
otherwise refuse to serve files in `assets/`.

---

## Reporting problems and contributing

If something does not work and the [Troubleshooting](#troubleshooting)
section does not help, please file an issue on the GitHub repository.
Include the relevant lines from your log file (with any passwords or
API keys removed) so we can see what the program was doing when it
failed.

Pull requests for bug fixes, documentation improvements, or new features
are welcome. Please run the test suite before submitting:

```
python3 -m pytest tests/
```

---

## License

This software is distributed under the terms of the license declared in
the `LICENSE` file in the project folder. If no `LICENSE` file is
present, please contact the project maintainer before using the
software outside your own institution.
