# belegmail

Fetch attachments from IMAP and store them. Use ``pip install -e .`` to install.

## Example configuration

```
- name: example
  config:
    imap:
      server: mail.example.org
      port: 993
      ssl: true
      username: username
      password: PASSWORT
      debug: true

    access:
      from: 
        - some@example.org
        - other@example.org
      to:
        - belege@example.org

    store:
      module: directory
      path: "/home/user/win/cloud/Buchhaltung/DATEV Belegtransfer/Company/Rechnungseingang"
      tag: example
```
