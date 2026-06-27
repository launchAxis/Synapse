#!/bin/sh
cd "$(dirname "$0")/../../terminal-ui" || exit 1
npm start -- "$@"
