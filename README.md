# belegmail

Fetch attachments from IMAP and store them. Use ``pip install -e .`` to install.

## Example configuration

````yaml
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

- name: nextcloud-example
  config:
    imap: # ...
  
    access: # ...
  
    store:
      module: nextcloud
      path: "https://cloud.example.org/remote.php/dav/files/someuser/Rechnungseingang/"
      tag: example
      username: someuser
      password: hunter2
````
