#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import textwrap

import click
import pyperclip

PROGRAM_NAME = 'bashelp'
PROGRAM_VERSION = '1.0'
USER_DATA_FOLDER = os.path.expanduser("~") + '/.' + PROGRAM_NAME
DATABASE_PATH = USER_DATA_FOLDER + '/CommandsDatabase.db'
TMPFILE_PATH = '/tmp/' + PROGRAM_NAME + '_TempCommandFile.txt'

# ~ Costanti tutto maiuscolo+underscore
# ~ Funzioni in maiuscolo, il resto in camelcase con l'iniziale minuscola
# ~ Tabelle in maiuscolo, colonne in camelcase con l'iniziale minuscola
# ~ I comandi vengono sempre stampati nel colore di default della shell
# ~ Le comunicazioni buone sono verdi, quelle cattive sono rosse

global dbConnection, db


def OpenDatabase():
    global dbConnection, db
    dbConnection = sqlite3.connect(DATABASE_PATH)
    db = dbConnection.cursor()
    db.execute('PRAGMA foreign_keys=ON')


def DatabaseCommandExists(commandId):
    exists = db.execute('SELECT count(*) FROM Commands WHERE rowid=?', (commandId,)).fetchone()[0]
    return (False, True)[exists]


def DatabaseAddCommand(commandId, command, description):
    if commandId != -1:
        db.execute('INSERT INTO Commands (rowid,command,description) VALUES(?,?,?)', (commandId, command, description))
    else:
        db.execute('INSERT INTO Commands (command,description) VALUES(?,?)', (command, description))
    commandId = db.lastrowid
    return commandId


def DatabaseRemoveCommand(commandId):  # non controlla che commandId esista
    db.execute('DELETE FROM Commands WHERE rowid=?', (commandId,))  # ON DELETE CASCADE removes all corresponding tags
    return 0


def DatabaseAddTag(tag, commandId):  # non controlla che commandId esista
    db.execute("INSERT INTO Tags (tag,commandId) VALUES(?,?)", (tag, commandId))
    return db.lastrowid


def DatabaseCommandSimilarity(
        command):  # Ci sono molte euristiche papabili per valutare la somiglianza! Questa è proprio di base
    prefixLength = min(len(command) // 2, 7)
    return db.execute("SELECT rowid,command,description FROM Commands WHERE command LIKE ?",
                      (command[:prefixLength] + '%',)).fetchall()


ISTTY = sys.stdout.isatty()
COLOR_BLUE = '\033[36m' if ISTTY else ''
COLOR_GREEN = '\033[92m' if ISTTY else ''
COLOR_RED = '\033[91m' if ISTTY else ''
COLOR_YELLOW = '\033[33m' if ISTTY else ''
COLOR_DEFAULT = '\033[0m' if ISTTY else ''
colors = {'blue': COLOR_BLUE, 'green': COLOR_GREEN, 'red': COLOR_RED, 'yellow': COLOR_YELLOW, 'default': COLOR_DEFAULT}


def ColorPrint(string, mainColor='default', prefix='', suffix='', backgroundColor='default', end='\n'):
    print(colors[backgroundColor] + prefix + colors[mainColor] + string + colors[backgroundColor] + suffix + colors[
        'default'], end=end)


def PrintCommand(commandId, command, description='', tags=[], ShowTags=False):
    ColorPrint(str(commandId), 'red', '', ': ', backgroundColor='default', end='')
    if command.count('\n') > 0:
        print('')
    ColorPrint(str(command), 'yellow')
    descriptionPrefix = '\t'
    descriptionWrapper = textwrap.TextWrapper(initial_indent=descriptionPrefix, subsequent_indent=' ' * (
            len(textwrap.fill(descriptionPrefix + '$', replace_whitespace=False)) - 1), width=70)
    if description != '':
        ColorPrint(descriptionWrapper.fill(description), 'blue')
    if ShowTags:
        coloredTags = map(lambda tag: COLOR_GREEN + tag + COLOR_DEFAULT, tags)
        tagsPrefix = '\ttags: '
        tagsWrapper = textwrap.TextWrapper(initial_indent=tagsPrefix, subsequent_indent=' ' * (
                len(textwrap.fill(tagsPrefix + '$', replace_whitespace=False)) - 1), width=90)
        print(tagsWrapper.fill(', '.join(coloredTags)))


def GetCommandFromDatabase(commandId):
    (command, description) = db.execute('SELECT command, description FROM Commands WHERE rowid=?',
                                        (commandId,)).fetchone()
    return command, description


def PrintCommandFromDatabase(commandId, ShowTags=False):  # Non controlla che il comando esista
    command, description = GetCommandFromDatabase(commandId)
    if ShowTags:
        tags = list(map(lambda x: x[0], db.execute('SELECT tag FROM Tags WHERE commandId=?', (commandId,)).fetchall()))
        PrintCommand(commandId, command, description, tags, True)
    else:
        PrintCommand(commandId, command, description)
    return command


def CheckSimilarity(command, description):
    similarCommands = DatabaseCommandSimilarity(command)
    if not similarCommands:
        return 1

    for (commandId2, command2, description2) in similarCommands:
        if command2 == command:
            ColorPrint("You wanted to add the command:", 'red')
            PrintCommand('TOADD', command)
            ColorPrint("but it is already saved, so it won't be added as a copy.", 'red')
            return False

    print("The command you want to add is:\n")
    PrintCommand('TOADD', command, description)
    print("\nbut it seems similar to these commands:\n")
    for (commandId2, command2, description2) in similarCommands:
        PrintCommand(commandId2, command2, description2)

    userAnswer = input("\nDo you want to add it anyway? (yes,no) ").lstrip().rstrip()
    while userAnswer != 'yes' and userAnswer != 'no':  # TODO: Exit after three attempts
        ColorPrint("\nThe only possible answers are yes and no.", 'red')
        userAnswer = input("Do you want to add it anyway? (yes,no) ").lstrip().rstrip()
    if userAnswer == 'yes':
        print('')  # Newline
        return True
    else:
        return False


COMMAND_TXT = 'Command (write it in the next line(s)).'
DESCRIPTION_TXT = 'Description: '
TAGS_TXT = 'Tags (each tag on a new line, starting from next line):\n'


def AddCommandFromFile(commandId, fileName):
    inputFile = open(fileName)
    regexp_s = fr'{re.escape(COMMAND_TXT)}\n([\s\S]*?)\n{re.escape(DESCRIPTION_TXT)}(.*?)\n{re.escape(TAGS_TXT)}([\s\S]+)'
    regexp = re.compile(regexp_s, re.MULTILINE)
    s = str(inputFile.read())
    command = regexp.search(s).group(1)
    description = regexp.search(s).group(2)
    tags = [s.rstrip().lstrip() for s in regexp.search(s).group(3).split('\n')]
    tags = [s for s in tags if s != '']
    if len(command) == 0:
        ColorPrint('The command must contain at least 1 character.', 'red')
        inputFile.close()
        return -1
    if len(description) < 5:
        ColorPrint('The description must contain at least 5 characters.', 'red')
        inputFile.close()
        return -1
    if not CheckSimilarity(command, description):
        inputFile.close()
        return -1
    inputFile.readline()
    inputFile.close()

    if not tags:
        ColorPrint('At least one tag must be specified.', 'red')
        return -1

    # print(f'command = "{command}"')
    # print(f'description = "{description}"')
    # print(f'tags = {tags}')
    commandId = DatabaseAddCommand(commandId, command, description)
    for tag in tags:
        DatabaseAddTag(tag, commandId)

    return commandId


def WriteCommandToFile(commandId, fileName):  # Non controllo l'esistenza di commandId
    outputFile = open(fileName, 'w+')
    (command, description) = db.execute('SELECT command, description FROM Commands WHERE rowid=?',
                                        (commandId,)).fetchone()
    outputFile.write(COMMAND_TXT + '\n' + command + '\n')
    outputFile.write(DESCRIPTION_TXT + description + '\n')
    outputFile.write(TAGS_TXT)
    allTags = db.execute('SELECT tag FROM Tags WHERE commandId=?', (commandId,)).fetchall()
    for (tag,) in allTags:
        outputFile.write(tag + '\n')
    outputFile.close()


def Uninstall():  # debugClean
    if (not os.path.exists(USER_DATA_FOLDER)):
        ColorPrint(PROGRAM_NAME + ' is not installed.', 'red')
        return
    shutil.rmtree(USER_DATA_FOLDER)
    ColorPrint(PROGRAM_NAME + ' has been uninstalled successfully.', 'green')


def Install():
    global dbConnection, db

    os.makedirs(USER_DATA_FOLDER)

    OpenDatabase()
    db.execute('''
		CREATE TABLE IF NOT EXISTS Commands(
			rowid INTEGER PRIMARY KEY AUTOINCREMENT,
			command TEXT UNIQUE NOT NULL, 
			description TEXT
		)
	''')
    db.execute('''
		CREATE TABLE IF NOT EXISTS Tags(
			tag TEXT NOT NULL, 
			commandId INTEGER, 
			FOREIGN KEY(commandId)
				REFERENCES Commands(rowid)
				ON DELETE CASCADE
				ON UPDATE CASCADE
		)
	''')
    dbConnection.commit()
    dbConnection.close()


#	Number of commands
#
#	command1
#	descrition1
#	number of tags
#	tag1
#	...
#	tagn
#
#	command2
#	...
def Import(fileName):
    inputFile = open(fileName)
    commandsNumber = int(inputFile.readline())
    importedCommandsNumber = 0
    print('There are ' + str(commandsNumber) + ' commands to be imported:\n')
    inputFile.readline()

    for i in range(commandsNumber):
        command = inputFile.readline().rstrip().lstrip()
        description = inputFile.readline().rstrip().lstrip()
        if not command:
            ColorPrint("The " + str(i) + "-th command doesn't contain any characters, then the command is skipped.",
                       'red')
            continue
        if len(description) < 5:
            ColorPrint("The description of the " + str(
                i) + "-th command is shorter than 5 characters, then the command is skipped.", 'red')
            continue

        toBeAdded = CheckSimilarity(command, description)
        commandId = 0
        if toBeAdded:
            commandId = DatabaseAddCommand(-1, command, description)

        n = int(inputFile.readline())
        for j in range(n):
            tag = inputFile.readline().rstrip().lstrip()
            if not toBeAdded:
                continue
            if not tag:
                ColorPrint("The " + str(j) + "-th tag of the " + str(
                    i) + "-th command doesn't contain any characters, then the tag is skipped.", 'red')
                continue
            DatabaseAddTag(tag, commandId)
        ColorPrint(command, 'default', 'The command ', ' was' + ('' if toBeAdded else ' not') + ' added.\n', 'blue')
        if toBeAdded:
            importedCommandsNumber += 1
        inputFile.readline()

    inputFile.close();
    ColorPrint(str(importedCommandsNumber) + ' commands were imported from the file ' + fileName + '.', 'green')


def Export(fileName):
    outputFile = open(fileName, 'w+')
    allCommands = db.execute('SELECT rowid,command,description FROM Commands').fetchall()
    outputFile.write(str(len(allCommands)) + '\n\n')
    for (commandId, command, description) in allCommands:
        outputFile.write(command + '\n')
        outputFile.write(description + '\n')
        allTags = db.execute('SELECT tag FROM Tags WHERE commandId=?', (commandId,)).fetchall()
        outputFile.write(str(len(allTags)) + '\n')
        for (tag,) in allTags:
            outputFile.write(tag + '\n')
        outputFile.write('\n')
        print('Command ' + str(commandId) + ' has been written to the file.')

    outputFile.close()
    ColorPrint('The whole database has been exported into ' + fileName + '.', 'green')


def Add():
    tmpFile = open(TMPFILE_PATH, 'w+')
    tmpFile.write(COMMAND_TXT + '\n' + DESCRIPTION_TXT + '\n' + TAGS_TXT)
    tmpFile.close()

    subprocess.check_call(['vim', TMPFILE_PATH])
    # subprocess.check_call(['nano', '-t', '+1,' + str(len(COMMAND_TXT) + 1), TMPFILE_PATH])

    commandId = AddCommandFromFile(-1, TMPFILE_PATH)
    if commandId != -1:
        print('The following command has been added: ')
        PrintCommandFromDatabase(commandId, 1)
    os.remove(TMPFILE_PATH)


def Remove(commandId):
    if not DatabaseCommandExists(commandId):
        ColorPrint("The command " + str(commandId) + " doesn't exist.", 'red')
        return 1
    print('The following command has been removed:')
    PrintCommandFromDatabase(commandId, 1)
    DatabaseRemoveCommand(commandId)


def Modify(commandId):
    if not DatabaseCommandExists(commandId):
        ColorPrint("The command " + str(commandId) + " doesn't exist.", 'red')
        return 1

    WriteCommandToFile(commandId, TMPFILE_PATH)
    DatabaseRemoveCommand(commandId)

    # subprocess.check_call(['nano', '-t', '+1,' + str(len(COMMAND_TXT) + 1), TMPFILE_PATH])
    subprocess.check_call(['vim', TMPFILE_PATH])
    commandId = AddCommandFromFile(commandId, TMPFILE_PATH)

    if commandId != -1:
        print('The command has been modified successfully: ')
        PrintCommandFromDatabase(commandId, 1)

    os.remove(TMPFILE_PATH)


def Show():
    allCommands = db.execute('SELECT rowid FROM Commands').fetchall()

    for (commandId,) in allCommands:
        PrintCommandFromDatabase(commandId, 1)
        print('')  # Newline

    if not allCommands:
        ColorPrint("There aren't commands saved. To add a command use " + PROGRAM_NAME + " --add", 'red')


def Search(commandTags):
    listOfCommandIdLists = []
    i = 0
    for tag in commandTags:
        commandIdList = list(set(db.execute("SELECT commandId FROM Tags WHERE tag LIKE ?", (commandTags[i] + '%',)).fetchall()))
        listOfCommandIdLists.append(commandIdList)
        i += 1
    from functools import reduce
    commandIdList = reduce(set.intersection, [set(l_) for l_ in listOfCommandIdLists])
    print('--------------------------------bashelp results---------------------------------')
    for (commandId,) in commandIdList:
        print('')
        command = PrintCommandFromDatabase(commandId, ShowTags=True)
        if len(commandIdList) == 1:
            pyperclip.copy(command)
            print('command copied into the clipboard')
    if len(commandIdList) > 1:
        try:
            selectedCommandId = click.prompt('Choose one id', type=int)
        except click.exceptions.Abort:
            return

        found = False
        for (commandId,) in commandIdList:
            command, _ = GetCommandFromDatabase(commandId)
            if selectedCommandId == commandId:
                pyperclip.copy(command)
                print('command copied into the clipboard')
                if found:
                    ColorPrint('Found more than one command matching the id', 'red')
                found = True
        if not found:
            ColorPrint('No command matches the selected id', 'red')

    if not commandIdList:
        ColorPrint("No command matches the tag searched.", 'red')


# Controllare la sicurezza del tutto e testare grandemente todos!
# Creare un sito di sharing -- ottimo ma esagerato
# Creare una gui testuale con ncurses al posto di aprire nano -- ottimo ma difficile da implementare rispetto al reale giovamento
# Aggiungere la possibilità di selezionare un comando e scriverlo senza dare invio -- ottimo ma come si fa a scrivere senza dare invio
# Aggiungere il parametro opzionale basedir ad un comando -- buono e facile
# Scrivendo solo bashelp parte la modalità interattiva -- fichissimo ma difficile da implementare
# Trasformare flag in comandi, git style -- argparse lo fa con i subparser/subcommands
# bashelp, shelp (con richiamo a shelf), memosh
# Usare distutils per installare
# Usare bashelp search per cercare, impostando l'autocompletamento
# La libreria click sembra fare questo e molto di più!


if __name__ == '__main__':
    if not os.path.exists(USER_DATA_FOLDER):
        Install()

    parser = argparse.ArgumentParser(description='Bookmark, tag and search your favourite shell commands.',
                                     epilog='Please see ' + PROGRAM_NAME + '(1) man pages for full documentation.')
    group = parser.add_mutually_exclusive_group(required=True)

    group.add_argument('--debugClean', action='store_true', default=False,
                       help='uninstall ' + PROGRAM_NAME)

    group.add_argument('--import', dest='fileImport', metavar='fileName', action='store', nargs=1, default='',
                       help='import from a file')
    group.add_argument('--export', dest='fileExport', metavar='fileName', action='store', nargs=1, default='',
                       help='export to a file')

    group.add_argument('--add', '-a', action='store_true', default=False,
                       help='add a new command')
    group.add_argument('--remove', '-r', metavar='commandId', nargs=1, type=int, action='store', default=-1,
                       help='remove a command, passed its id')
    group.add_argument('--modify', '-m', metavar='commandId', nargs=1, type=int, action='store', default=-1,
                       help='modify a command, passed its id')

    group.add_argument('--show', '-s', action='store_true', default=False,
                       help='show all commands saved, with descriptions and tags')

    group.add_argument('tags', metavar='TAGS', action='store', nargs='*', default='',
                       help='tag(s) to be searched')

    group.add_argument('--version', '-v', action='version', version=PROGRAM_NAME + ' ' + PROGRAM_VERSION)

    args = parser.parse_args()

    OpenDatabase()

    if args.fileImport:
        Import(args.fileImport[0])
        dbConnection.commit()
    elif args.fileExport:
        Export(args.fileExport[0])
    elif args.add:
        Add()
        dbConnection.commit()
    elif args.remove != -1:
        Remove(args.remove[0])
        dbConnection.commit()
    elif args.modify != -1:
        Modify(args.modify[0])
        dbConnection.commit()
    elif args.show:
        Show()
    elif args.tags:
        Search(args.tags)
    elif args.debugClean:
        Uninstall()
    dbConnection.close()
