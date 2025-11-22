#!/bin/sh
# convert .zip file(s) info .sfs image(s)

set -e

export PATH="/usr/bin:/bin"

WORKDIR="/tmp"

for zip_path in "$@"; do
    zip_file=${zip_path##*/}
    zip_name=${zip_file%.*}

    extract="$WORKDIR/${zip_name}.zip2sfs/"
    result="${zip_name}.sfs"

    unzip -n "${zip_path}" -d "${extract}"
    mksquashfs "${extract}" "${result}" -noappend

    chown --reference="${zip_path}" "${result}"
    chmod --reference="${zip_path}" "${result}"
    touch --reference="${zip_path}" "${result}"

    rm -rf "${extract}"
done

exit 0
