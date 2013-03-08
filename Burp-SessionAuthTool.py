# This Burp extensions provides passive and active scanner checks for
# detection of potential privilege escalation issues caused by
# transmission of user identifiers from the client.

from burp import (IBurpExtender, ITab, IScannerCheck, IScanIssue)
from javax.swing import (JPanel, JTable, JButton, JTextField, JLabel, JScrollPane)
from javax.swing.table import AbstractTableModel
from java.awt import (GridBagLayout, GridBagConstraints)
from java.util import ArrayList

class BurpExtender(IBurpExtender, ITab, IScannerCheck):
    def registerExtenderCallbacks(self, callbacks):
        self.burp = callbacks
        self.helpers = callbacks.getHelpers()
        callbacks.setExtensionName("Session Authentication Tool")
        self.out = callbacks.getStdout()

        # definition of suite tab
        self.tab = JPanel(GridBagLayout())
        self.tabledata = MappingTableModel()
        self.table = JTable(self.tabledata)
        #self.table.getColumnModel().getColumn(0).setPreferredWidth(50);
        #self.table.getColumnModel().getColumn(1).setPreferredWidth(100);
        self.tablecont = JScrollPane(self.table)
        c = GridBagConstraints()
        c.fill = GridBagConstraints.HORIZONTAL
        c.anchor = GridBagConstraints.FIRST_LINE_START
        c.gridx = 0
        c.gridy = 0
        c.gridheight = 6
        c.weightx = 0.3
        c.weighty = 0.5
        self.tab.add(self.tablecont, c)

        c = GridBagConstraints()
        c.weightx = 0.1
        c.anchor = GridBagConstraints.FIRST_LINE_START
        c.gridx = 1

        c.gridy = 0
        label_id = JLabel("Identifier:")
        self.tab.add(label_id, c)
        self.input_id = JTextField(20)
        self.input_id.setToolTipText("Enter the identifier which is used by the application to identifiy a particular test user account, e.g. a numerical user id or a user name.")
        c.gridy = 1
        self.tab.add(self.input_id, c)

        c.gridy = 2
        label_content = JLabel("Content:")
        self.tab.add(label_content, c)
        self.input_content = JTextField(20, actionPerformed=self.btn_add_id)
        self.input_content.setToolTipText("Enter some content which is displayed in responses of the application and shows that the current session belongs to a particular user, e.g. the full name of the user.")
        c.gridy = 3
        self.tab.add(self.input_content, c)

        self.btn_add = JButton("Add/Edit Identity", actionPerformed=self.btn_add_id)
        c.gridy = 4
        self.tab.add(self.btn_add, c)

        self.btn_del = JButton("Delete Identity", actionPerformed=self.btn_del_id)
        c.gridy = 5
        self.tab.add(self.btn_del, c)

        callbacks.customizeUiComponent(self.tab)
        callbacks.customizeUiComponent(self.table)
        callbacks.customizeUiComponent(self.tablecont)
        callbacks.customizeUiComponent(self.btn_add)
        callbacks.customizeUiComponent(self.btn_del)
        callbacks.customizeUiComponent(label_id)
        callbacks.customizeUiComponent(self.input_id)
        callbacks.addSuiteTab(self)
        callbacks.registerScannerCheck(self)

    def btn_add_id(self, e):
        ident = self.input_id.text
        self.input_id.text = ""
        content = self.input_content.text
        self.input_content.text = ""
        self.tabledata.add_mapping(ident, content)
        self.input_id.requestFocusInWindow()

    def btn_del_id(self, e):
        rows = self.table.getSelectedRows().tolist()
        self.tabledata.del_rows(rows)

    ### ITab ###
    def getTabCaption(self):
        return("SessionAuth")

    def getUiComponent(self):
        return self.tab

    ### IScannerCheck ###
    def doPassiveScan(self, baseRequestResponse):
        analyzedRequest = self.helpers.analyzeRequest(baseRequestResponse)
        params = analyzedRequest.getParameters()
        ids = self.tabledata.getIds()
        issues = list()

        for param in params:
            value = param.getValue()
            for ident in ids:
                if value == ident:
                    issues.append(SessionAuthPassiveScanIssue(
                        baseRequestResponse.getHttpService(),
                        analyzedRequest.getUrl(),
                        baseRequestResponse,
                        param,
                        ident,
                        self.tabledata.getValue(ident),
                        SessionAuthPassiveScanIssue.foundEqual
                        ))
                elif value.find(ident) >= 0:
                    issues.append(SessionAuthPassiveScanIssue(
                        baseRequestResponse.getHttpService(),
                        analyzedRequest.getUrl(),
                        baseRequestResponse,
                        param,
                        ident,
                        self.tabledata.getValue(ident),
                        SessionAuthPassiveScanIssue.foundInside
                        ))
        if len(issues) > 0:
            return issues
        else:
            return None

    def doActiveScan(self, baseRequestResponse, insertionPoint):
        return None

    def consolidateDuplicateIssues(self, existingIssue, newIssue):
        return 0


class SessionAuthPassiveScanIssue(IScanIssue):
    foundEqual = 1                        # parameter value equals identifier
    foundInside = 2                       # identifier was found inside parameter value

    def __init__(self, service, url, httpmsgs, param, ident, value, foundtype):
        self.service = service
        self.findingurl = url
        self.httpmsgs = [httpmsgs]
        self.param = param
        self.ident = ident
        self.value = value
        self.foundtype = foundtype

    def getUrl(self):
        return self.findingurl

    def getIssueName(self):
        return "Object Identifier found in Parameter Value"

    def getIssueType(self):
        return 1

    def getSeverity(self):
        return "Information"

    def getConfidence(self):
        if self.foundtype == self.foundEqual:
            return "Certain"
        elif self.foundtype == self.foundInside:
            return "Tentative"

    def getIssueDetail(self):
        msg = "The parameter <b>" + self.param.getName() + "</b> contains the user identifier <b>" + self.param.getValue() + "</b>."
        if "".join(map(chr, self.httpmsgs[0].getResponse())).find(self.value):
            msg += "\nThe value <b>" + self.value + "</b> associated with the identifier was found in the response. The request is \
            probably suitable for active scan detection of privilege escalation vulnerabilities."
        return msg

    def getRemediationDetail(self):
        return None

    def getIssueBackground(self):
        return "User identifiers submitted in requests are potential targets for parameter tampering attacks. An attacker could try to impersonate other users by \
        replacement of his own user identifier by the id from a different user. This issue was reported because the user identifier previously entered was found in \
        the request."

    def getRemediationBackground(self):
        return "Normally it is not necessary to submit the user identifier in requests to identitfy the user account associated with a session. The user identity should \
        be stored in session data. There are some legitime cases where user identifiers are submitted in requests, e.g. logins or viewing profiles of other users."

    def getHttpMessages(self):
        return self.httpmsgs

    def getHttpService(self):
        return self.service


class MappingTableModel(AbstractTableModel):
    def __init__(self):
        AbstractTableModel.__init__(self)
        self.columnnames = ["User/Object Identifier", "Content"]
        self.mappings = dict()
        self.idorder = list()

    def getColumnCount(self):
        return len(self.columnnames)

    def getRowCount(self):
        return len(self.mappings)

    def getColumnName(self, col):
        return self.columnnames[col]

    def getValueAt(self, row, col):
        if col == 0:
            return self.idorder[row]
        else:
            return self.mappings[self.idorder[row]]

    def getColumnClass(self, idx):
        return str

    def isCellEditable(self, row, col):
       if col < 1:
           return False
       else:
           return True

    def add_mapping(self, ident, content):
        if ident not in self.mappings:
            self.idorder.append(ident)
        self.mappings[ident] = content
        self.fireTableDataChanged()

    def del_rows(self, rows):
        rows.sort()
        deleted = 0
        for row in rows:
            del self.mappings[self.idorder[row - deleted]]
            if row - deleted > 0:
                self.idorder = self.idorder[:row - deleted] + self.idorder[row + 1 - deleted:]
            else:
                self.idorder = self.idorder[1:]
            self.fireTableRowsDeleted(row - deleted, row - deleted)
            deleted = deleted + 1

    def setValueAt(self, val, row, col):
        if col == 1:
            self.mappings[self.idorder[row]] = val
            self.fireTableCellUpdated(row, col)

    def getIds(self):
        return self.idorder

    def getValue(self, ident):
        return self.mappings[ident]