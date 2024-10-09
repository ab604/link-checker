
Last Updated on 2024-10-09

## Link checker

This repository contains `yaml` scripts to run Github Actions workflows
that check the status of links on websites. Feel free to fork and adapt.

The workflow runs as a `cron` job and checks the links on the named
website using Node.js
[linkinator](https://www.npmjs.com/package/linkinator) and creates a
`csv` report file of the links and their status, writes it to the
`reports` folder and also emails it.

If you are setting up multiple workflows so you can check different
websites, ensure their run times are sufficiently spaced so they aren’t
running at the same time or it will cause errors when they try to write
to the repo.

The linkinator author has made a ready-to-go [linkinator Github
Action](https://github.com/JustinBeckwith/linkinator-action) but for my
purposes I found it easier to install and cache it in the workflow.

For emailing the report, my Uni has locked off the ability to create app
passwords needed for the authentication, so I used a gmail account
instead.

## Github set-up

The workflow `yaml` is kept in `.github/workflows`

You’ll need to set up some secrets in your GitHub repository:

- `WEBSITE_URL`: The URL of your website to check. I’ve amended the name
  of this secret variable in the scripts here.

- `GMAIL_USERNAME` : Your gmail account in the form `me@gmail.com`

- `GMAIL_PASSWORD` : Your App Password. See [Create App
  passwords](https://knowledge.workspace.google.com/kb/how-to-create-app-passwords-000009237)

- `EMAIL_RECIPIENT` : email address you want to send the report to in
  the form `me@soton.ac.uk`

- `EMAIL_SENDER` : the gmail address you are sending from in the form
  `<me@gmail.com>`

## Outputs

The `csv` report file has four columns:

- `url` : the url of the link
- `status` : the [HTTP status
  code](https://developer.mozilla.org/en-US/docs/Web/HTTP/Status)
- `state` : a string `OK`, `BROKEN` or `SKIPPED`
- `parent` : the page url containing the link  
- `failureDetails` : `json` object
