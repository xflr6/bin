# bin

Command-line scripts (mostly \*nix).


## Installation

```sh
$ cd /usr/local/
$ git clone git@github.com:xflr6/bin.git
```


## Usage


### backup-squashfs.py

```sh
$ backup-squashfs.py --help
usage: backup-squashfs.py [-h] [--name TEMPLATE] [--exclude-file PATH]
                          [--comp {gzip,lzo,xz}] [--owner OWNER]
                          [--group GROUP] [--chmod MODE] [--set-path LINE]
                          [--set-umask MASK] [--quiet] [--ask-for-deletion]
                          [--version]
                          source_dir dest_dir

Create SquashFS image from given directory, optioally ask for its deletion.

positional arguments:
  source_dir            image source directory
  dest_dir              image target directory

optional arguments:
  -h, --help            show this help message and exit
  --name TEMPLATE       image filename datetime.strftime() format string
                        (default: %Y%m%d-%H%M.sfs)
  --exclude-file PATH   path to file with one line per blacklist item
  --comp {gzip,lzo,xz}  compression (use mksquashfs default if omitted)
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

```sh
$ backup-tar.py --help
usage: backup-tar.py [-h] [--name TEMPLATE] [--exclude-file PATH]
                     [--no-auto-compress] [--owner OWNER] [--group GROUP]
                     [--chmod MODE] [--set-path LINE] [--set-umask MASK]
                     [--ask-for-deletion] [--version]
                     source_dir dest_dir

Create tar archive from given directory, optionally ask for its deletion.

positional arguments:
  source_dir           archive source directory
  dest_dir             directory for tar archive

optional arguments:
  -h, --help           show this help message and exit
  --name TEMPLATE      archive filename datetime.strftime() format string
                       (default: %Y%m%d-%H%M.tar.gz)
  --exclude-file PATH  path to file with one line per blacklist item
  --no-auto-compress   don't pass --auto-compress to tar
  --owner OWNER        tar archive owner
  --group GROUP        tar archive group
  --chmod MODE         tar archive chmod (default: 400)
  --set-path LINE      PATH for tar subprocess (default: /usr/bin:/bin)
  --set-umask MASK     umask for tar subprocess (default: 177)
  --ask-for-deletion   prompt for tar archive deletion before exit
  --version            show program's version number and exit
```


### blame-wiki.py

```sh
$ blame-wiki.py --help
usage: blame-wiki.py [-h] [--export-url URL] [--version]
                     page_title search_string

Dump XML of first MediaWiki page revision containing a search string.

positional arguments:
  page_title        title of the page on MediaWiki
  search_string     string to match page wikitext

optional arguments:
  -h, --help        show this help message and exit
  --export-url URL  MediaWiki instance export url (default:
                    https://en.wikipedia.org/wiki/Special:Export)
  --version         show program's version number and exit
```


### count-wiki.py

```sh
$ count-wiki.py --help
usage: count-wiki.py [-h] [--tag TAG] [--display PATH] [--display-after N]
                     [--stop-after N] [--version]
                     filename

Count page tags in MediaWiki XML export.

positional arguments:
  filename           path to MediaWiki XML export (format: .xml.bz2)

optional arguments:
  -h, --help         show this help message and exit
  --tag TAG          end tag to count (default: mediawiki:page)
  --display PATH     ElementPath to log in sub-total (default:
                     mediawiki:title)
  --display-after N  log sub-total after N tags (default: 1000)
  --stop-after N     stop after N tags
  --version          show program's version number and exit
```


### dumpall-svn.py

```sh
$ dumpall-svn.py --help
usage: dumpall-svn.py [-h] [--name TEMPLATE] [--no-auto-compress]
                      [--no-deltas] [--chmod MODE] [--set-path LINE]
                      [--detail] [--verbose] [--version]
                      target_dir repo_dir [repo_dir ...]

Svnadmin dump subversion repositories into target directory.

positional arguments:
  target_dir          output directory for dump files
  repo_dir            subversion repository directory

optional arguments:
  -h, --help          show this help message and exit
  --name TEMPLATE     dump filename datetime.strftime() format string
                      (default: {name}.svndump.gz)
  --no-auto-compress  never compress dump file(s) (default: auto-compress if
                      --name ends with any of: .bz2, .gz, .xz)
  --no-deltas         don't pass --deltas to $(svnadmin dump)
  --chmod MODE        dump file chmod (default: 400)
  --set-path LINE     PATH for subprocess(es) (default: /usr/bin:/bin)
  --detail            include detail infos for each repository
  --verbose           don't pass --quiet to $(svnadmin dump)
  --version           show program's version number and exit
```


### pull-gists.py

```sh
$ pull-gists.py --help
usage: pull-gists.py [-h] [--reset] [--detail] [--version]
                     target_dir gh_username

Git clone --mirror or git remote update all public gists of GitHub user.

positional arguments:
  target_dir   output directory for bare git clones
  gh_username  GitHub username

optional arguments:
  -h, --help   show this help message and exit
  --reset      delete present git clones first
  --detail     show detailed info for each clone/update
  --version    show program's version number and exit
```


### pull-repos.py

```sh
$ pull-repos.py --help
usage: pull-repos.py [-h] [--reset] [--detail] [--version]
                     target_dir repo_url [repo_url ...]

Git clone --mirror or git remote update git repositories.

positional arguments:
  target_dir  output directory for bare git clones
  repo_url    git repository url

optional arguments:
  -h, --help  show this help message and exit
  --reset     delete present git clones first
  --detail    show detailed info for each clone/update
  --version   show program's version number and exit
```


## License

These scripts are distributed under the [MIT license][MIT]


[MIT]: https://opensource.org/licenses/MIT
