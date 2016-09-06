import csv
import locale
import os
import sys
from datetime import date, datetime, timedelta
from itertools import combinations
from StringIO import StringIO

def getInterestExpected(todayDate, partData):
    yesterday = todayDate - timedelta(1)
    fomDate = yesterday.replace(day=1)
    intDict = {}
    for part in partData:
        id = int(part["Id"])
        startDateOrig = datetime.strptime(part["Start Date"], "%d/%m/%Y").date()
        startDate = max(startDateOrig, fomDate)
        endDate = todayDate
        if part["End Date"]:
            endDateOrig = datetime.strptime(part["End Date"], "%d/%m/%Y").date()
            if endDateOrig <= todayDate:
                endDate = endDateOrig
        # huh?
        bonusDays = 1 if startDateOrig < fomDate and endDate < todayDate else 0
        if endDate > fomDate and startDate < todayDate:
            intDict[id] = ((((endDate - startDate).days + bonusDays) / 365.) * 0.12) * locale.atof(part["Amount"])
    return intDict

def getInterestActual(todayDate, txData):
    yesterday = todayDate - timedelta(1)
    fomDate = yesterday.replace(day=1)
    intDict = {}
    for part in txData:
        if not part["Transaction type"] == "Interest" or not part["Txn Date"] or not part["Loan part ID"]:
            continue
        txnDate = datetime.strptime(part["Txn Date"], "%d/%m/%Y").date()
        id = int(part["Loan part ID"])
        if txnDate < todayDate and txnDate >= fomDate:
            intDict[id] = float(part["Txn Amount"])
    return intDict

def getRecombinedInterest(recDate, partDataOrig, txData):
    expected = getInterestExpected(recDate, partDataOrig)
    actual = getInterestActual(recDate, txData)

    if sum(expected.values()) or sum(actual.values()):
        diffs = dict([(i, actual[i] - expected[i]) for i in expected if i in actual and abs(round(actual[i] - expected[i], 2)) > 0])

        partData = dict([(int(p["Id"]), p) for p in partDataOrig])
        fundData = dict([(int(p["Loan part ID"]), p) for p in txData if p["Transaction type"] == "Loan part fund"])
        combo = {}
        for d in diffs:
            origSize = abs(locale.atof(fundData[d]["Txn Amount"]))
            currSize = locale.atof(partData[d]["Amount"])
            loanName = partData[d]["Asset Details"]
            startDate = partData[d]["Start Date"]
            childAmounts = dict([(c, locale.atof(partData[c]["Amount"])) for c in partData if c not in fundData and c != d and partData[c]["Asset Details"] == loanName and partData[c]["Start Date"] == startDate])
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

def getTransactionTotal(txData, txType, valueType="Txn Amount"):
    txTotal = 0
    for part in txData:
        if part["Transaction type"] == txType:
            txTotal += locale.atof(part[valueType])
    return txTotal

def main():
    locale.setlocale(locale.LC_ALL, '' if os.name == "nt" else 'en_GB')
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
            if actual[a] != expected.get(a, 0):
                print "Rec Diff    %8d: Expected: %8.2f, Actual: %8.2f" % (a, expected.get(a, 0), actual[a])
        expectedTotal = round(sum(expected.values()), 2)
        actualTotal = round(sum(actual.values()), 2)
        print "Rec Total %s: Expected: %8.2f, Actual: %8.2f" % (recDate, expectedTotal, actualTotal)
        expectedLTD += expectedTotal
        actualLTD += actualTotal
        recDate = (recDate - timedelta(1)).replace(day=1)
    print "\nSUMMARY:"
    print "Expected total interest: %8.2f" % expectedLTD
    print "Actual total interest  : %8.2f" % actualLTD
    cashTotal = getTransactionTotal(txData, "Deposit") + getTransactionTotal(txData, "Withdrawal") + getTransactionTotal(txData, 'Affiliate credit')
    tradeTotal = getTransactionTotal(txData, "Capital repayment") + getTransactionTotal(txData, "Loan part sale") + getTransactionTotal(txData, "Loan part fund") 
    openBalance = getTransactionTotal(txData, "Opening Balance", "Balance")
    currBalance = getTransactionTotal(txData, "Available Balance", "Balance")
    print "\nBalance (expected interest + actual txn): %8.2f" % (openBalance + cashTotal + expectedLTD + tradeTotal)
    print "Balance (actual interest + actual txn)  : %8.2f" % (openBalance + cashTotal + actualLTD + tradeTotal)
    print "Statement balance                       : %8.2f" % currBalance

if __name__ == "__main__":
    main()
