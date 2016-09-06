import csv
import locale
import os
import sys
from datetime import date, datetime, timedelta
from itertools import combinations
from StringIO import StringIO

TYPE_FUND = "Loan part fund"
TYPE_SALE = "Loan part sale"
TYPE_INTEREST = "Interest"
TYPE_CAPITAL = "Capital repayment"
TYPE_DEPOSIT = "Deposit"
TYPE_WITHDRAWAL = "Withdrawal"
TYPE_OPENING = "Opening Balance"
TYPE_AVAILABLE = "Available Balance"
TYPE_CREDIT = "Affiliate credit"

ATTR_PARTID = "Id"
ATTR_PARTAMOUNT = "Amount"
ATTR_START_DATE = "Start Date"
ATTR_END_DATE = "End Date"
ATTR_DETAILS = "Asset Details"

ATTR_TXID = "Loan part ID"
ATTR_TXTYPE = "Transaction type"
ATTR_TXDATE = "Txn Date"
ATTR_TXAMOUNT = "Txn Amount"
ATTR_BALANCE = "Balance"

def getInterestExpected(todayDate, partData):
    yesterday = todayDate - timedelta(1)
    fomDate = yesterday.replace(day=1)
    intDict = {}
    for part in partData:
        id = int(part[ATTR_PARTID])
        startDateOrig = datetime.strptime(part[ATTR_START_DATE], "%d/%m/%Y").date()
        startDate = max(startDateOrig, fomDate)
        endDate = todayDate
        if part[ATTR_END_DATE]:
            endDateOrig = datetime.strptime(part[ATTR_END_DATE], "%d/%m/%Y").date()
            if endDateOrig <= todayDate:
                endDate = endDateOrig
        # huh?
        bonusDays = 1 if startDateOrig < fomDate and endDate < todayDate else 0
        if endDate > fomDate and startDate < todayDate:
            intDict[id] = ((((endDate - startDate).days + bonusDays) / 365.) * 0.12) * locale.atof(part[ATTR_PARTAMOUNT])
    return intDict

def getInterestActual(todayDate, txData):
    yesterday = todayDate - timedelta(1)
    fomDate = yesterday.replace(day=1)
    intDict = {}
    for part in txData:
        if not part[ATTR_TXTYPE] == TYPE_INTEREST or not part[ATTR_TXDATE] or not part[ATTR_TXID]:
            continue
        txnDate = datetime.strptime(part[ATTR_TXDATE], "%d/%m/%Y").date()
        id = int(part[ATTR_TXID])
        if txnDate < todayDate and txnDate >= fomDate:
            intDict[id] = float(part[ATTR_TXAMOUNT])
    return intDict

def getRecombinedInterest(recDate, partDataOrig, txData):
    expected = getInterestExpected(recDate, partDataOrig)
    actual = getInterestActual(recDate, txData)

    if sum(expected.values()) or sum(actual.values()):
        diffs = dict([(i, actual[i] - expected[i]) for i in expected if i in actual and abs(round(actual[i] - expected[i], 2)) > 0])

        partData = dict([(int(p[ATTR_PARTID]), p) for p in partDataOrig])
        fundData = dict([(int(p[ATTR_TXID]), p) for p in txData if p[ATTR_TXTYPE] == TYPE_FUND])
        combo = {}
        for d in diffs:
            origSize = abs(locale.atof(fundData[d][ATTR_TXAMOUNT]))
            currSize = locale.atof(partData[d][ATTR_PARTAMOUNT])
            loanName = partData[d][ATTR_DETAILS]
            startDate = partData[d][ATTR_START_DATE]
            childAmounts = dict([(c, locale.atof(partData[c][ATTR_PARTAMOUNT])) for c in partData if c not in fundData and c != d and partData[c][ATTR_DETAILS] == loanName and partData[c][ATTR_START_DATE] == startDate])
            i = 1
            while i <= len(childAmounts):
                for c in combinations(childAmounts.items(), i):
                    dc = dict(c)
                    diff = round(abs(origSize - round(currSize + sum(dc.values()), 2)), 2)
                    if diff == 0.0:
                        combo[d] = dc.keys()
                        break
                if d in combo:
                    break
                i += 1

        for c in combo:
            for k in combo[c]:
                if k not in actual and k in expected:
                    expected[c] += expected[k]
                    del expected[k]

        for c in expected:
            expected[c] = round(expected[c], 2)

    return expected, actual

def getTransactionTotal(txData, txType, valueType=ATTR_TXAMOUNT):
    txTotal = 0
    for part in txData:
        if part[ATTR_TXTYPE] == txType:
            txTotal += locale.atof(part[valueType])
    return txTotal
    
def checkDuplicates(txData, txType):
    x = [part[ATTR_TXID] for part in txData if part[ATTR_TXTYPE] == txType]
    y = set([i for i in x if x.count(i) > 1])
    return y

def checkAllDuplicates(txData):
    dupeResults = {}
    for dupeType in [TYPE_SALE, TYPE_FUND, TYPE_CAPITAL]:
        dupes = checkDuplicates(txData, dupeType)
        dupeResults[dupeType] = dupes
    return dupeResults
    
def main():
    locale.setlocale(locale.LC_ALL, "" if os.name == "nt" else "en_GB")
    partFile = sys.argv[1]
    txFile = sys.argv[2]
    with open(partFile, "r") as f:
       partData = [i for i in csv.DictReader(StringIO(f.read()))]
    with open(txFile, "r") as f:
       txData = [i for i in csv.DictReader(StringIO(f.read()))]
    recDate = date.today().replace(day=1)
    expectedLTD = 0
    actualLTD = 0
    while True:
        expected, actual = getRecombinedInterest(recDate, partData, txData)
        if not sum(expected.values()) and not sum(actual.values()):
            break
        print "\nRec Date: %s" % recDate
        for c in expected:
            if expected[c] != actual.get(c, 0):
                print "Rec Diff    %8d: Expected: %8.2f, Actual: %8.2f" % (c, expected[c], actual.get(c, 0))
        for a in actual:
            if a not in expected:
                print "Rec Diff    %8d: Expected: %8.2f, Actual: %8.2f" % (a, 0, actual[a])
        expectedTotal = round(sum(expected.values()), 2)
        actualTotal = round(sum(actual.values()), 2)
        print "Rec Total %s: Expected: %8.2f, Actual: %8.2f" % (recDate, expectedTotal, actualTotal)
        expectedLTD += expectedTotal
        actualLTD += actualTotal
        recDate = (recDate - timedelta(1)).replace(day=1)
    print
    print "Expected total interest: %8.2f" % expectedLTD
    print "Actual total interest  : %8.2f" % actualLTD
    print
    dupeResults = checkAllDuplicates(txData)
    for dupeType, dupes in dupeResults.items():
        if dupes:
            print "Duplicate %ss: %s" % (dupeType.lower(), ", ".join(dupes))
        else:
            print "No duplicate %ss" % dupeType.lower()
    cashTotal = getTransactionTotal(txData, TYPE_DEPOSIT) + getTransactionTotal(txData, TYPE_WITHDRAWAL) + getTransactionTotal(txData, TYPE_CREDIT)
    tradeTotal = getTransactionTotal(txData, TYPE_CAPITAL) + getTransactionTotal(txData, TYPE_SALE) + getTransactionTotal(txData, TYPE_FUND) 
    openBalance = getTransactionTotal(txData, TYPE_OPENING, ATTR_BALANCE)
    currBalance = getTransactionTotal(txData, TYPE_AVAILABLE, ATTR_BALANCE)
    print
    print "Balance (expected interest + actual txn): %8.2f" % (openBalance + cashTotal + expectedLTD + tradeTotal)
    print "Balance (actual interest + actual txn)  : %8.2f" % (openBalance + cashTotal + actualLTD + tradeTotal)
    print "Statement balance                       : %8.2f" % currBalance

if __name__ == "__main__":
    main()