
Last Updated on 2024-10-09

## Link checker

This repository contains `yaml` scripts to run Github Actions workflows
that check the status of links on websites. Feel free to fork and adapt.

The workflow checks the links on the named website using node.js
[linkinator](https://www.npmjs.com/package/linkinator) and creates a
`csv` file of the links and their status, and then emails it.
