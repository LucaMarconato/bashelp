bashelp
=======
"A tool for bookmarking and tagging your favourite (and impossible to remember) shell commands", forked from [dario2994](https://github.com/dario2994/bashelp).

This fork
======

New features brought by this fork:

- you can save commands spanning multiple lines (like code snippets);
- the retrieved commands are automatically copied into the clipboard;
- improved way in which commands are presented and selected by the user upon search.

30 seconds demo:

[![30 seconds video showing a demo of bashelp](https://img.youtube.com/vi/CbDKKno5-p8/0.jpeg)](https://www.youtube.com/watch?v=CbDKKno5-p8)

Installation
============
1. Clone the repository or just download the whole content in a folder on your pc.
2. Execute in a shell 'sudo ./install.sh'.

Now you have installed bashelp.
To remove bashelp just execute 'uninstall.sh'.

Usage
=====
With
```bash
bashelp -a
```
you can interactively **a**dd a command to your shelf,
then get it with
```bash
bashelp <command_tag>
```
If you need to **m**odify a command, use
```bash
bashelp -m <command_id>
```
(the command id is shown by `bashelp <command_tag>`).
You can also **r**emove commands with
```bash
bashelp -r <command_id>
```

For further information you may use 
```bash
bashelp -h
```
or read the documentation in the manual
```bash
man bashelp
```
