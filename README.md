# bin

[![Build](https://github.com/xflr6/bin/actions/workflows/build.yaml/badge.svg?branch=master)](https://github.com/xflr6/bin/actions/workflows/build.yaml?query=branch%3Amaster)
[![Coverage](https://codecov.io/gh/xflr6/bin/branch/master/graph/badge.svg)](https://codecov.io/gh/xflr6/bin)

Command-line scripts (mostly \*nix).


## Installation

```shell
$ (cd /usr/local && git clone git@github.com:xflr6/bin.git)
```


## Usage


### backup-squashfs.py

```shell
$ backup-squashfs.py --help
usage: backup-squashfs.py [-h] [--name TEMPLATE] [--exclude-file PATH]
                          [--comp {gzip,lz4,lzo,xz,zstd}] [--owner OWNER]
                          [--group GROUP] [--chmod MODE] [--set-path LINE]
                          [--set-umask MASK] [--quiet] [--ask-for-deletion]
                          [--version]
                          source_dir dest_dir

Create SquashFS image from given directory, optionally ask for its deletion.

positional arguments:
  source_dir            input root directory to image
  dest_dir              output directory for writing the SquashFS image file

options:
  -h, --help            show this help message and exit
  --name TEMPLATE       image file name time.strftime() format string template
                        (default: %Y%m%d-%H%M.sfs)
  --exclude-file PATH   path to file with one line per excluded dir/file
  --comp {gzip,lz4,lzo,xz,zstd}
                        compression (use mksquashfs default if omitted)
  --owner OWNER         image file owner
  --group GROUP         image file group
  --chmod MODE          image file chmod (default: 400)
  --set-path LINE       PATH for mksquashfs subprocess (default: /usr/bin)
  --set-umask MASK      umask for mksquashfs subprocess (default: 177)
  --quiet               suppress stdout and stderr of mksquashfs subprocess
  --ask-for-deletion    prompt for image file deletion before exit
  --version             show program's version number and exit
```


### backup-tar.py

```shell
$ backup-tar.py --help
usage: backup-tar.py [-h] [--name TEMPLATE] [--exclude-file PATH]
                     [--no-auto-compress] [--owner OWNER] [--group GROUP]
                     [--chmod MODE] [--set-path LINE] [--set-umask MASK]
                     [--ask-for-deletion] [--version]
                     source_dir dest_dir

Create tar archive from given directory, optionally ask for its deletion.

positional arguments:
  source_dir           input root directory to archive
  dest_dir             output directory for writing the tar archive file

options:
  -h, --help           show this help message and exit
  --name TEMPLATE      archive file name time.strftime() format string
                       template (default: %Y%m%d-%H%M.tar.gz)
  --exclude-file PATH  path to file with one line per excluded dir/file
  --no-auto-compress   don't pass --auto-compress to tar
  --owner OWNER        archive file owner
  --group GROUP        archive file group
  --chmod MODE         archive file chmod (default: 400)
  --set-path LINE      PATH for tar subprocess (default: /usr/bin:/bin)
  --set-umask MASK     umask for tar subprocess (default: 177)
  --ask-for-deletion   prompt for archive file deletion before exit
  --version            show program's version number and exit
```


### download-podcasts.py

```shell
$ download-podcasts.py --help
usage: download-podcasts.py [-h] [--config PATH] [--encoding NAME] [--limit N]
                            [--serial] [--verbose]
                            [section ...]

Download podcast episodes from subscriptions in config file sections.

positional arguments:
  section          config section name of podcast to download

options:
  -h, --help       show this help message and exit
  --config PATH    INI file with one section per podcast subscription, result
                   paths relative to its directory (default: podcasts.ini)
  --encoding NAME  config file encoding (default: utf-8)
  --limit N        number of episodes to download (overrides --config file)
  --serial         don't parallelize downloads from different sections
  --verbose        log skipping of downloads that match present files
```


### fix-dropbox-overlays.py

```shell
$ fix-dropbox-overlays.py --help
usage: fix-dropbox-overlays.py [-h] [--dry-run] [--version]

Fix Dropbox update messing up Toirtoise* overlay handlers in Windows registry.

options:
  -h, --help  show this help message and exit
  --dry-run   show what would be changed (don't write to registry)
  --version   show program's version number and exit
```


### git-pull-gists.py

```shell
$ git-pull-gists.py --help
usage: git-pull-gists.py [-h] [--reset] [--detail] [--version]
                         target_dir gh_username

Git clone --mirror or git remote update all public Gists of GitHub user.

positional arguments:
  target_dir   output directory for writing/updating bare Git clones
  gh_username  name of the GitHub user account

options:
  -h, --help   show this help message and exit
  --reset      delete present Git clones first
  --detail     show detailed info for each clone/update
  --version    show program's version number and exit
```


### git-pull-repos.py

```shell
$ git-pull-repos.py --help
usage: git-pull-repos.py [-h] [--reset] [--detail] [--version]
                         target_dir repo_url [repo_url ...]

Git clone --mirror or git remote update remote Git repositories.

positional arguments:
  target_dir  output directory for writing/updating bare Git clones
  repo_url    input Git repository URL

options:
  -h, --help  show this help message and exit
  --reset     delete present Git clones first
  --detail    show detailed info for each clone/update
  --version   show program's version number and exit
```


### log-pings.py

```shell
$ log-pings.py --help
usage: log-pings.py [-h] [--host IP] [--file LOGFILE] [--format TMPL]
                    [--datefmt TMPL] [--ipfmt TMPL] [--icmpfmt TMPL]
                    [--setuid USER] [--chroot DIR] [--no-hardening]
                    [--encoding NAME] [--max-size N] [--verbose] [--version]

Log incoming ICMP echo request messages to stdout and optionally into file.

options:
  -h, --help       show this help message and exit
  --host IP        address to listen on (default: 0.0.0.0)
  --file LOGFILE   file to write log to (log only to stdout by default)
  --format TMPL    log format (default: %(asctime)s%(ip)s%(icmp)s %(message)s)
  --datefmt TMPL   log time.strftime() format (default: %b %d %H:%M:%S)
  --ipfmt TMPL     log format (default: %(src)s:%(ident)d)
  --icmpfmt TMPL   log format (default: %(ident)d:%(seq_num)d)
  --setuid USER    user to setuid to after binding (default: nobody)
  --chroot DIR     directory to chroot into after binding (default: /tmp)
  --no-hardening   don't give up privileges (ignore --setuid and --chroot)
  --encoding NAME  try to decode data with this encoding (default: utf-8)
  --max-size N     payload byte limit for packages to process (default: 1472)
  --verbose        increase stdout logging level to DEBUG
  --version        show program's version number and exit
```


### log-udp.py

```shell
$ log-udp.py --help
usage: log-udp.py [-h] [--host IP] [--port SERVICE] [--file LOGFILE]
                  [--format TMPL] [--datefmt TMPL] [--setuid USER]
                  [--chroot DIR] [--no-hardening] [--encoding NAME]
                  [--verbose] [--version]

Log incoming UDP messages to stdout and optionally into file.

options:
  -h, --help       show this help message and exit
  --host IP        address to listen on (default: 0.0.0.0)
  --port SERVICE   UDP port number or name to listen on (default: discard)
  --file LOGFILE   file to write log to (log only to stdout by default)
  --format TMPL    log format string (default: %(asctime)s %(message)s)
  --datefmt TMPL   log time.strftime() format string (default: %b %d %H:%M:%S)
  --setuid USER    user to setuid to after binding (default: nobody)
  --chroot DIR     directory to chroot into after binding (default: /tmp)
  --no-hardening   don't give up privileges (ignore --setuid and --chroot)
  --encoding NAME  encoding of UDP messages (default: utf-8)
  --verbose        increase stdout logging level to DEBUG
  --version        show program's version number and exit
```


### pdflatex-nup.py

```shell
$ pdflatex-nup.py --help
usage: pdflatex-nup.py [-h] [--name TMPL] [--paper SIZE] [--nup XxY]
                       [--pages RANGE] [--orient {l,p,a}] [--scale FACTOR]
                       [--no-frame] [--no-openright] [--keep] [--version]
                       pdf_file

Compile a 2up version of a PDF file using LaTeX pdfpages' \includepdfmerge.
See also https://github.com/DavidFirth/pdfjam

positional arguments:
  pdf_file          name of the source PDF file for \includepdfmerge

options:
  -h, --help        show this help message and exit
  --name TMPL       template for nup PDF file (default: {stem}_2up.pdf)
  --paper SIZE      output LaTeX paper size (default: a4)
  --nup XxY         nup option for \includepdfmerge (default: 2x1)
  --pages RANGE     pages option for \includepdfmerge (default: -)
  --orient {l,p,a}  l(andscape), p(ortrait), a(uto) (default: a)
  --scale FACTOR    scale option for \includepdfmerge (default: 1.01)
  --no-frame        don't pass frame option to \includepdfmerge
  --no-openright    don't pass openright option to \includepdfmerge
  --keep            don't delete intermediate files (*.tex, *.log, etc.)
  --version         show program's version number and exit
```


### serve-asciimation.py

```shell
$ serve-asciimation.py --help
usage: serve-asciimation.py [-h] [--host IP] [--port SERVICE] [--fps N]
                            [--setuid USER] [--chroot DIR] [--no-hardening]
                            [--verbose] [--version]

Run async server displaying asciimation via telnet.

options:
  -h, --help      show this help message and exit
  --host IP       address to listen on (default: 127.0.0.1)
  --port SERVICE  TCP port number or name to listen on (default: telnet)
  --fps N         frames (1-100) per second to generate (default: 15)
  --setuid USER   user to setuid to after binding (default: nobody)
  --chroot DIR    directory to chroot into after binding (default: /tmp)
  --no-hardening  don't give up privileges (ignore --setuid and --chroot)
  --verbose       increase stdout logging level to DEBUG
  --version       show program's version number and exit
```


### shasum-update.py

```shell
$ shasum-update.py --help
usage: shasum-update.py [-h] [--target TEXT_FILE] [--encoding NAME]
                        [--pattern REGEX] [--confirm]
                        glob [glob ...]

SHA256sum file(s) and update text file with regex locating name and hash.

positional arguments:
  glob                glob pattern of file(s) to checksum

options:
  -h, --help          show this help message and exit
  --target TEXT_FILE  path to the text file to be updated
  --encoding NAME     target text file read/write encoding (default: utf-8)
  --pattern REGEX     re.sub() pattern with file and checksum group
  --confirm           prompt for confirmation before exit when updated
```


### svn-dumpall.py

```shell
$ svn-dumpall.py --help
usage: svn-dumpall.py [-h] [--name TEMPLATE] [--no-auto-compress]
                      [--no-deltas] [--chmod MODE] [--set-path LINE]
                      [--detail] [--verbose] [--version]
                      target_dir repo_dir [repo_dir ...]

Svnadmin dump Subversion repositories into target directory.

positional arguments:
  target_dir          output directory for writing SVN dump file(s)
  repo_dir            input SVN repository directory

options:
  -h, --help          show this help message and exit
  --name TEMPLATE     dump file name time.strftime() format string template
                      (default: {name}.svndump.gz)
  --no-auto-compress  never compress dump file(s) (default: auto-compress if
                      --name ends with any of: .bz2, .gz, .lz4, .lzo, .xz,
                      .zst)
  --no-deltas         don't pass --deltas to svnadmin dump
  --chmod MODE        dump file(s) chmod (default: 400)
  --set-path LINE     PATH for subprocess(es) (default: /usr/bin:/bin)
  --detail            include detail infos for each repository
  --verbose           don't pass --quiet to svnadmin dump
  --version           show program's version number and exit
```


### wiki-blame.py

```shell
$ wiki-blame.py --help
usage: wiki-blame.py [-h] [--export-url URL] [--version]
                     page_title search_string

Dump XML of first MediaWiki page revision containing a search string.

positional arguments:
  page_title        title of the page on MediaWiki
  search_string     string to match page wikitext

options:
  -h, --help        show this help message and exit
  --export-url URL  MediaWiki instance export url (default:
                    https://en.wikipedia.org/wiki/Special:Export)
  --version         show program's version number and exit
```


### wiki-count.py

```shell
$ wiki-count.py --help
usage: wiki-count.py [-h] [--tag TAG] [--stats] [--stats-top N]
                     [--display PATH] [--display-after N] [--stop-after N]
                     [--version]
                     filename

Count page tags in MediaWiki XML export.

positional arguments:
  filename           path to MediaWiki XML export (format: .xml.bz2)

options:
  -h, --help         show this help message and exit
  --tag TAG          end tag to count (default: mediawiki:page)
  --stats            also compute and display page edit statistics
  --stats-top N      show top N users edits and lines (default: 100)
  --display PATH     ElementPath to log in sub-total (default:
                     mediawiki:title)
  --display-after N  log sub-total after N tags (default: 1000)
  --stop-after N     stop after N tags
  --version          show program's version number and exit
```


## License

These scripts are distributed under the [MIT license][MIT]


[MIT]: https://opensource.org/licenses/MIT
