import csv
import logging
import locale
import os
import sys
from datetime import date, datetime, timedelta
from itertools import combinations
from StringIO import StringIO

def getInterestCalc(todayDate, partData):
    yesterday = todayDate - timedelta(1)
    fomDate = yesterday.replace(day=1)
    intDict = {}
    for part in csv.DictReader(StringIO(partData)):
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
    for part in csv.DictReader(StringIO(txData)):
        if not part["Transaction type"] == "Interest" or not part["Txn Date"] or not part["Loan part ID"]:
            continue
        txnDate = datetime.strptime(part["Txn Date"], "%d/%m/%Y").date()
        id = int(part["Loan part ID"])
        if txnDate < todayDate and txnDate >= fomDate:
            intDict[id] = float(part["Txn Amount"])
    return intDict

def getRecombinedInterest(recDate, partFile, txFile):
    with open(partFile, "r") as f:
       partDataOrig = f.read()
    with open(txFile, "r") as f:
       txData = f.read()
    calc = getInterestCalc(recDate, partDataOrig)
    actual = getInterestActual(recDate, txData)

    if sum(calc.values()) or sum(actual.values()):
        diffs = dict([(i, actual[i] - calc[i]) for i in calc if i in actual and abs(round(actual[i] - calc[i], 2)) > 0])

        partData = dict([(int(p["Id"]), p) for p in csv.DictReader(StringIO(partDataOrig))])
        fundData = dict([(int(p["Loan part ID"]), p) for p in csv.DictReader(StringIO(txData)) if p["Transaction type"] == "Loan part fund"])
        combo = {}
        for d in diffs:
            origSize = abs(float(fundData[d]["Txn Amount"]))
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
                if k not in actual and k in calc:
                    calc[c] += calc[k]
                    del calc[k]

        for c in calc:
            calc[c] = round(calc[c], 2)

    return calc, actual

def main():
    logging.basicConfig(format="%(asctime)s: %(msg)s")
    locale.setlocale(locale.LC_ALL, '' if os.name == "nt" else 'en_GB')
    partFile = sys.argv[1]
    txFile = sys.argv[2]
    recDate = date.today().replace(day=1)
    while True:
        calc, actual = getRecombinedInterest(recDate, partFile, txFile)
        if not sum(calc.values()) and not sum(actual.values()):
            break
        print "\nRec Date: %s" % recDate
        errors = []
        for c in calc:
            if calc[c] != actual.get(c, 0):
                print "Rec Failure %8d: Calc: %8.2f, Actual: %8.2f" % (c, calc[c], actual.get(c, 0))
        for a in actual:
            if actual[a] != calc.get(a, 0):
                print "Rec Failure %8d: Calc: %8.2f, Actual: %8.2f" % (a, calc.get(a, 0), actual[a])
        calcTotal = round(sum(calc.values()), 2)
        actualTotal = round(sum(actual.values()), 2)
        print "Rec Total %s: Calc: %8.2f, Actual: %8.2f" % (recDate, calcTotal, actualTotal)
        recDate = (recDate - timedelta(1)).replace(day=1)

if __name__ == "__main__":
    main()