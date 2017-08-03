#!/usr/bin/env python
__author__ = "Gao Wang"
__copyright__ = "Copyright 2016, Stephens lab"
__email__ = "gaow@uchicago.edu"
__license__ = "MIT"
import json
import pickle
import os

HOME_DOC = '''
This page displays contents of DSC database `NAME`. There are two types of tables in this database:

* **pipeline** tables: *add description*
* **module** tables: *add description*

[DSC script](#DSC-script) that generated this database can be found at the end of this page.
'''

def write_notebook(text, output, execute = True):
    import nbformat
    nb = nbformat.reads(text, as_version = 4)
    if execute:
        from nbconvert.preprocessors import ExecutePreprocessor
        ep = ExecutePreprocessor(timeout=600, kernel_name='SoS')
        ep.preprocess(nb, {})
    with open(os.path.expanduser(output), 'wt') as f:
        nbformat.write(nb, f)

def get_database_summary(db, output, title = "Database Summary", description = None):
    jc = JupyterComposer()
    jc.add("# {}\n{}".format(title,
                             '\n\n'.join(description) if description is not None
                             else HOME_DOC.replace("NAME", os.path.basename(db))))
    jc.add('''
import pickle
data = pickle.load(open("{}", 'rb'))
    '''.format(os.path.expanduser(db)), cell = "code", out = False)
    data = pickle.load(open(os.path.expanduser(db), 'rb'))
    jc.add("## Pipelines")
    for key in data:
        if key.startswith('pipeline_') and not key.endswith(".captain"):
            captain = data[key + '.captain']
            jc.add("### pipeline{} `{}`\nExecuted pipelines:\n{}".\
                   format('s' if len(captain) > 1 else '', key[9:],
                          '\n'.join(['* ' + ' + '.join(["`{}`".format(x) for x in seq]) for seq in captain])))
            jc.add("%preview -n data['{0}']".format(key), cell = "code")
    jc.add("## Modules")
    for key in data:
        if not key.startswith("pipeline_") and not key.startswith('.'):
            jc.add("### module `{}`".format(key))
            jc.add("%preview -n data['{}']".format(key), cell = "code")
    jc.add("## DSC script")
    jc.add("```yaml\n{}\n```".format(eval(data['.dscsrc'])))
    write_notebook(jc.dump(), output)

def get_query_summary(db, output, title, description = None):
    jc = JupyterComposer()
    jc.add("# {}\n{}".format(title,
                             '\n\n'.join(description) if description is not None
                             else ''))
    jc.add('''
import pickle
info = pickle.load(open("{}", 'rb'))
    '''.format(os.path.expanduser(db)), cell = "code", out = False)
    info = pickle.load(open(os.path.expanduser(db), 'rb'))
    i = 0
    for d, q in zip(info['data'], info['queries']):
        jc.add("## Pipeline {}".format(i + 1))
        jc.add("```sql\n{}\n```".format(q), out = False)
        jc.add("%preview -n info['data'][{}]".format(i), cell = "code")
        i += 1
    write_notebook(jc.dump(), output)

class JupyterComposer:
    def __init__(self):
        self.text = ['{\n "cells": [']
        self.has_end = False

    def add(self, content, cell = "markdown", kernel = "SoS", out = True):
        content = [x + '\n' for x in content.strip().split("\n")]
        content[-1] = content[-1].rstrip('\n')
        self.text.append('  {\n   "cell_type": "%s",%s\n   %s\n   %s"source": %s' \
                         % (cell, '\n   "execution_count": null,' if cell == "code" else '',
                            self.get_metadata(cell, kernel, out),
                            '"outputs": [],\n   'if cell == 'code' else '',
                            json.dumps(content)))
        self.text.append("  },")

    def dump(self):
        if not self.has_end:
            self.text.append(self.get_footer())
            self.has_end = True
        return '\n'.join(self.text)

    def get_footer(self):
        self.text[-1] = self.text[-1].rstrip().rstrip(',')
        return ''' ],
 "metadata": {
  "anaconda-cloud": {},
  "celltoolbar": "Tags",
  "kernelspec": {
   "display_name": "SoS",
   "language": "sos",
   "name": "sos"
  },
  "language_info": {
   "codemirror_mode": "sos",
   "file_extension": ".sos",
   "mimetype": "text/x-sos",
   "name": "sos",
   "nbconvert_exporter": "sos.jupyter.converter.SoS_Exporter",
   "pygments_lexer": "sos"
  },
  "sos": {
   "kernels": [],
   "panel": {
    "displayed": true,
    "height": 0,
    "style": "side"
   }
  }
 },
 "nbformat": 4,
 "nbformat_minor": 2
}'''

    @staticmethod
    def get_metadata(cell, kernel, out):
        def get_tag():
            if cell == 'code' and out:
                return "report_output"
            elif cell == 'markdown' and not out:
                return "hide_output"
        #
        out = '"metadata": {\n    "collapsed": false,\n    "kernel": "%s",\n    "scrolled": true,\n    "tags": ["%s"]\n   },' % (kernel, get_tag())
        return out

if __name__ == '__main__':
    # jc = JupyterComposer()
    # jc.add("# Title")
    # jc.add("print(666)", cell = 'code', kernel = 'SoS')
    # jc.add("print(999)", cell = 'code', kernel = 'SoS', out = True)
    # print(jc.dump())
    import sys
    get_database_summary(sys.argv[1], sys.argv[2])