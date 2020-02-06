# bin

Command-line scripts (\*nix).


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
                          [--set-umask MASK] [--keep] [--quiet] [--version]
                          source dest

Create SquashFS image from given directory and prompt for its deletion.

positional arguments:
  source                image source directory
  dest                  image target directory

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
  --keep                don't prompt for image file deletion (exit directly)
  --quiet               suppress stdout and stderr of mksquashfs subprocess
  --version             show program's version number and exit
```
