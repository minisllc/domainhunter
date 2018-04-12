#!/usr/bin/env python

## Title:       domainhunter.py
## Author:      @joevest and @andrewchiles
## Description: Checks expired domains, reputation/categorization, and Archive.org history to determine 
##              good candidates for phishing and C2 domain names
# Add OCR support for BlueCoat/SiteReview CAPTCHA using tesseract
# Add support for input file list of potential domains
# Add additional error checking for ExpiredDomains.net parsing
# Changed -q/--query switch to -k/--keyword to better match its purpose
import time 
import random
import argparse
import json
import base64

__version__ = "20180411"

## Functions

def doSleep(timing):
    if timing == 0:
        time.sleep(random.randrange(90,120))
    elif timing == 1:
        time.sleep(random.randrange(60,90))
    elif timing == 2:
        time.sleep(random.randrange(30,60))
    elif timing == 3:
        time.sleep(random.randrange(10,20))
    elif timing == 4:
        time.sleep(random.randrange(5,10))
    # There's no elif timing == 5 here because we don't want to sleep for -t 5

def checkBluecoat(domain):
    try:
        url = 'https://sitereview.bluecoat.com/resource/lookup'
        postData = {'url':domain,'captcha':''}   # HTTP POST Parameters
        headers = {'User-Agent':useragent,
                    'Content-Type':'application/json; charset=UTF-8',
                    'Referer':'https://sitereview.bluecoat.com/lookup'}

        print('[*] BlueCoat: {}'.format(domain))
        response = s.post(url,headers=headers,json=postData,verify=False)
        responseJSON = json.loads(response.text)

        if 'errorType' in responseJSON:
            a = responseJSON['errorType']
        else:
            a = responseJSON['categorization'][0]['name']
        
        # Print notice if CAPTCHAs are blocking accurate results and attempt to solve if --ocr
        if a == 'captcha':
            if ocr:
                # This request is performed in a browser, but is not needed for our purposes
                #captcharequestURL = 'https://sitereview.bluecoat.com/resource/captcha-request'
                #print('[*] Requesting CAPTCHA')
                #response = s.get(url=captcharequestURL,headers=headers,cookies=cookies,verify=False)

                print('[*] Received CAPTCHA challenge!')
                captcha = solveCaptcha('https://sitereview.bluecoat.com/resource/captcha.jpg',s)
                
                if captcha:
                    b64captcha = base64.b64encode(captcha.encode('utf-8')).decode('utf-8')
                   
                    # Send CAPTCHA solution via GET since inclusion with the domain categorization request doens't work anymore
                    captchasolutionURL = 'https://sitereview.bluecoat.com/resource/captcha-request/{0}'.format(b64captcha)
                    print('[*] Submiting CAPTCHA at {0}'.format(captchasolutionURL))
                    response = s.get(url=captchasolutionURL,headers=headers,verify=False)

                    # Try the categorization request again
                    response = s.post(url,headers=headers,json=postData,verify=False)

                    responseJSON = json.loads(response.text)

                    if 'errorType' in responseJSON:
                        a = responseJSON['errorType']
                    else:
                        a = responseJSON['categorization'][0]['name']
                else:
                    print('[-] Error: Failed to solve BlueCoat CAPTCHA with OCR! Manually solve at "https://sitereview.bluecoat.com/sitereview.jsp"')
            else:
                print('[-] Error: BlueCoat CAPTCHA received. Try --ocr flag or manually solve a CAPTCHA at "https://sitereview.bluecoat.com/sitereview.jsp"')

        return a

    except Exception as e:
        print('[-] Error retrieving Bluecoat reputation! {0}'.format(e))
        return "-"

def checkIBMXForce(domain):
    try: 
        url = 'https://exchange.xforce.ibmcloud.com/url/{}'.format(domain)
        headers = {'User-Agent':useragent,
                    'Accept':'application/json, text/plain, */*',
                    'x-ui':'XFE',
                    'Origin':url,
                    'Referer':url}

        print('[*] IBM xForce: {}'.format(domain))

        url = 'https://api.xforce.ibmcloud.com/url/{}'.format(domain)
        response = s.get(url,headers=headers,verify=False)

        responseJSON = json.loads(response.text)

        if 'error' in responseJSON:
            a = responseJSON['error']

        elif not responseJSON['result']['cats']:
            a = 'Uncategorized'
        
        else:
            categories = ''
            # Parse all dictionary keys and append to single string to get Category names
            for key in responseJSON["result"]['cats']:
                categories += '{0}, '.format(str(key))

            a = '{0}(Score: {1})'.format(categories,str(responseJSON['result']['score']))

        return a

    except:
        print('[-] Error retrieving IBM x-Force reputation!')
        return "-"

def checkTalos(domain):
    url = "https://www.talosintelligence.com/sb_api/query_lookup?query=%2Fapi%2Fv2%2Fdetails%2Fdomain%2F&query_entry={0}&offset=0&order=ip+asc".format(domain)
    headers = {'User-Agent':useragent,
               'Referer':url}

    print('[*] Cisco Talos: {}'.format(domain))
    try:
        response = s.get(url,headers=headers,verify=False)

        responseJSON = json.loads(response.text)

        if 'error' in responseJSON:
            a = str(responseJSON['error'])
        
        elif responseJSON['category'] is None:
            a = 'Uncategorized'

        else:
            a = '{0} (Score: {1})'.format(str(responseJSON['category']['description']), str(responseJSON['web_score_name']))
       
        return a

    except:
        print('[-] Error retrieving Talos reputation!')
        return "-"

def checkMXToolbox(domain):
    url = 'https://mxtoolbox.com/Public/Tools/BrandReputation.aspx'
    headers = {'User-Agent':useragent,
            'Origin':url,
            'Referer':url}  

    print('[*] Google SafeBrowsing and PhishTank: {}'.format(domain))
    
    try:
        response = s.get(url=url, headers=headers)
        
        soup = BeautifulSoup(response.content,'lxml')

        viewstate = soup.select('input[name=__VIEWSTATE]')[0]['value']
        viewstategenerator = soup.select('input[name=__VIEWSTATEGENERATOR]')[0]['value']
        eventvalidation = soup.select('input[name=__EVENTVALIDATION]')[0]['value']

        data = {
        "__EVENTTARGET": "",
        "__EVENTARGUMENT": "",
        "__VIEWSTATE": viewstate,
        "__VIEWSTATEGENERATOR": viewstategenerator,
        "__EVENTVALIDATION": eventvalidation,
        "ctl00$ContentPlaceHolder1$brandReputationUrl": domain,
        "ctl00$ContentPlaceHolder1$brandReputationDoLookup": "Brand Reputation Lookup",
        "ctl00$ucSignIn$hfRegCode": 'missing',
        "ctl00$ucSignIn$hfRedirectSignUp": '/Public/Tools/BrandReputation.aspx',
        "ctl00$ucSignIn$hfRedirectLogin": '',
        "ctl00$ucSignIn$txtEmailAddress": '',
        "ctl00$ucSignIn$cbNewAccount": 'cbNewAccount',
        "ctl00$ucSignIn$txtFullName": '',
        "ctl00$ucSignIn$txtModalNewPassword": '',
        "ctl00$ucSignIn$txtPhone": '',
        "ctl00$ucSignIn$txtCompanyName": '',
        "ctl00$ucSignIn$drpTitle": '',
        "ctl00$ucSignIn$txtTitleName": '',
        "ctl00$ucSignIn$txtModalPassword": ''
        }
          
        response = s.post(url=url, headers=headers, data=data)

        soup = BeautifulSoup(response.content,'lxml')

        a = ''
        if soup.select('div[id=ctl00_ContentPlaceHolder1_noIssuesFound]'):
            a = 'No issues found'
            return a
        else:
            if soup.select('div[id=ctl00_ContentPlaceHolder1_googleSafeBrowsingIssuesFound]'):
                a = 'Google SafeBrowsing Issues Found. '
        
            if soup.select('div[id=ctl00_ContentPlaceHolder1_phishTankIssuesFound]'):
                a += 'PhishTank Issues Found'
            return a

    except Exception as e:
        print('[-] Error retrieving Google SafeBrowsing and PhishTank reputation!')
        return "-"

def downloadMalwareDomains(malwaredomainsURL):
    url = malwaredomainsURL
    response = s.get(url=url,headers=headers,verify=False)
    responseText = response.text
    if response.status_code == 200:
        return responseText
    else:
        print("[-] Error reaching:{}  Status: {}").format(url, response.status_code)

def checkDomain(domain):
    print('[*] Fetching domain reputation for: {}'.format(domain))

    if domain in maldomainsList:
        print("[!] {}: Identified as known malware domain (malwaredomains.com)".format(domain))
    
    mxtoolbox = checkMXToolbox(domain)
    print("[+] {}: {}".format(domain, mxtoolbox))
    
    bluecoat = checkBluecoat(domain)
    print("[+] {}: {}".format(domain, bluecoat))
    
    ibmxforce = checkIBMXForce(domain)
    print("[+] {}: {}".format(domain, ibmxforce))

    ciscotalos = checkTalos(domain)
    print("[+] {}: {}".format(domain, ciscotalos))
    print("")
    return

def solveCaptcha(url,session):  
    # Downloads CAPTCHA image and saves to current directory for OCR with tesseract
    # Returns CAPTCHA string or False if error occured
    jpeg = 'captcha.jpg'
    try:
        response = session.get(url=url,headers=headers,verify=False, stream=True)
        if response.status_code == 200:
            with open(jpeg, 'wb') as f:
                response.raw.decode_content = True
                shutil.copyfileobj(response.raw, f)
        else:
            print('[-] Error downloading CAPTCHA file!')
            return False

        text = pytesseract.image_to_string(Image.open(jpeg))
        text = text.replace(" ", "")
        return text
    except Exception as e:
        print("[-] Error solving CAPTCHA - {0}".format(e))
        return False

## MAIN
if __name__ == "__main__":

    parser = argparse.ArgumentParser(description='Finds expired domains, domain categorization, and Archive.org history to determine good candidates for C2 and phishing domains')
    parser.add_argument('-k','--keyword', help='Keyword used to refine search results', required=False, default=False, type=str, dest='keyword')
    parser.add_argument('-c','--check', help='Perform domain reputation checks', required=False, default=False, action='store_true', dest='check')
    parser.add_argument('-f','--filename', help='Specify input file of line delimited domain names to check', required=False, default=False, type=str, dest='filename')
    parser.add_argument('--ocr', help='Perform OCR on CAPTCHAs when present', required=False, default=False, action='store_true')
    parser.add_argument('-r','--maxresults', help='Number of results to return when querying latest expired/deleted domains', required=False, default=100, type=int, dest='maxresults')
    parser.add_argument('-s','--single', help='Performs detailed reputation checks against a single domain name/IP.', required=False, default=False, dest='single')
    parser.add_argument('-t','--timing', help='Modifies request timing to avoid CAPTCHAs. Slowest(0) = 90-120 seconds, Default(3) = 10-20 seconds, Fastest(5) = no delay', required=False, default=3, type=int, choices=range(0,6), dest='timing')
    parser.add_argument('-w','--maxwidth', help='Width of text table', required=False, default=400, type=int, dest='maxwidth')
    parser.add_argument('-V','--version', action='version',version='%(prog)s {version}'.format(version=__version__))
    args = parser.parse_args()

    # Load dependent modules
    try:
        import requests
        from bs4 import BeautifulSoup
        from texttable import Texttable
        
    except Exception as e:
        print("Expired Domains Reputation Check")
        print("[-] Missing basic dependencies: {}".format(str(e)))
        print("[*] Install required dependencies by running `pip3 install -r requirements.txt`")
        quit(0)

    # Load OCR related modules if --ocr flag is set since these can be difficult to get working
    if args.ocr:
        try:
            import pytesseract
            from PIL import Image
            import shutil
        except Exception as e:
            print("Expired Domains Reputation Check")
            print("[-] Missing OCR dependencies: {}".format(str(e)))
            print("[*] Install required Python dependencies by running `pip3 install -r requirements.txt`")
            print("[*] Ubuntu\Debian - Install tesseract by running `apt-get install tesseract-ocr python3-imaging`")
            print("[*] MAC OSX - Install tesseract with homebrew by running `brew install tesseract`")
            quit(0)

## Variables
    keyword = args.keyword

    check = args.check

    filename = args.filename
    
    maxresults = args.maxresults
    
    single = args.single

    timing = args.timing

    maxwidth = args.maxwidth
    
    malwaredomainsURL = 'http://mirror1.malwaredomains.com/files/justdomains'
    expireddomainsqueryURL = 'https://www.expireddomains.net/domain-name-search'
    
    ocr = args.ocr

    timestamp = time.strftime("%Y%m%d_%H%M%S")
            
    useragent = 'Mozilla/5.0 (compatible; MSIE 10.0; Windows NT 6.1; WOW64; Trident/6.0)'
    headers = {'User-Agent':useragent}

    requests.packages.urllib3.disable_warnings()
 
    # HTTP Session container, used to manage cookies, session tokens and other session information
    s = requests.Session()

    data = []

    title = '''
 ____   ___  __  __    _    ___ _   _   _   _ _   _ _   _ _____ _____ ____  
|  _ \ / _ \|  \/  |  / \  |_ _| \ | | | | | | | | | \ | |_   _| ____|  _ \ 
| | | | | | | |\/| | / _ \  | ||  \| | | |_| | | | |  \| | | | |  _| | |_) |
| |_| | |_| | |  | |/ ___ \ | || |\  | |  _  | |_| | |\  | | | | |___|  _ < 
|____/ \___/|_|  |_/_/   \_\___|_| \_| |_| |_|\___/|_| \_| |_| |_____|_| \_\ '''

    print(title)
    print("")
    print("Expired Domains Reputation Checker")
    print("Authors: @joevest and @andrewchiles\n")
    print("DISCLAIMER: This is for educational purposes only!")
    disclaimer = '''It is designed to promote education and the improvement of computer/cyber security.  
The authors or employers are not liable for any illegal act or misuse performed by any user of this tool.
If you plan to use this content for illegal purpose, don't.  Have a nice day :)'''
    print(disclaimer)
    print("")

    # Download known malware domains
    print('[*] Downloading malware domain list from {}\n'.format(malwaredomainsURL))
    maldomains = downloadMalwareDomains(malwaredomainsURL)
    maldomainsList = maldomains.split("\n")

    # Retrieve reputation for a single choosen domain (Quick Mode)
    if single:
        checkDomain(single)
        quit(0)

    # Perform detailed domain reputation checks against input file
    if filename:
        try:
            with open(filename, 'r') as domainsList:
                for line in domainsList.read().splitlines():
                    checkDomain(line)
                    doSleep(timing)
        except KeyboardInterrupt:
            print('Caught keyboard interrupt. Exiting!')
            quit(0)
        except Exception as e:
            print('[-] {}'.format(e))
            quit(1)
        quit(0)
     
    # Generic Proxy support 
    # TODO: add as a parameter 
    proxies = {
      'http': 'http://127.0.0.1:8080',
      'https': 'http://127.0.0.1:8080',
    }

    # Create an initial session
    domainrequest = s.get("https://www.expireddomains.net",headers=headers,verify=False)
    
    # Use proxy like Burp for debugging request/parsing errors
    #domainrequest = s.get("https://www.expireddomains.net",headers=headers,verify=False,proxies=proxies)

    # Generate list of URLs to query for expired/deleted domains
    urls = []
    domain_list = []

    # Use the keyword string to narrow domain search if provided
    if keyword:
        print('[*] Fetching expired or deleted domains containing "{}"'.format(keyword))
        for i in range (0,maxresults,25):
            if i == 0:
                urls.append("{}/?q={}".format(expireddomainsqueryURL,keyword))
                headers['Referer'] ='https://www.expireddomains.net/domain-name-search/?q={}&start=1'.format(keyword)
            else:
                urls.append("{}/?start={}&q={}".format(expireddomainsqueryURL,i,keyword))
                headers['Referer'] ='https://www.expireddomains.net/domain-name-search/?start={}&q={}'.format((i-25),keyword)
    
    # If no keyword provided, retrieve list of recently expired domains in batches of 25 results.
    else:
        print('[*] Fetching expired or deleted domains...')
        # Caculate number of URLs to request since we're performing a request for four different resources instead of one
        numresults = int(maxresults / 4)
        for i in range (0,(numresults),25):
            urls.append('https://www.expireddomains.net/backorder-expired-domains?start={}&o=changed&r=a'.format(i))
            urls.append('https://www.expireddomains.net/deleted-com-domains/?start={}&o=changed&r=a'.format(i))
            urls.append('https://www.expireddomains.net/deleted-net-domains/?start={}&o=changed&r=a'.format(i))
            urls.append('https://www.expireddomains.net/deleted-org-domains/?start={}&o=changed&r=a'.format(i))
    
    for url in urls:

        print("[*]  {}".format(url))

        # Annoyingly when querying specific keywords the expireddomains.net site requires additional cookies which 
        #  are set in JavaScript and not recognized by Requests so we add them here manually.
        # May not be needed, but the _pk_id.10.dd0a cookie only requires a single . to be successful
        # In order to somewhat match a real cookie, but still be different, random integers are introduced

        r1 = random.randint(100000,999999)


        # Known good example _pk_id.10.dd0a cookie: 5abbbc772cbacfb1.1496760705.2.1496760705.1496760705
        pk_str = '5abbbc772cbacfb1' + '.1496' + str(r1) + '.2.1496' + str(r1) + '.1496' + str(r1)

        jar = requests.cookies.RequestsCookieJar()
        jar.set('_pk_ses.10.dd0a', '*', domain='expireddomains.net', path='/')
        jar.set('_pk_id.10.dd0a', pk_str, domain='expireddomains.net', path='/')
        
        domainrequest = s.get(url,headers=headers,verify=False,cookies=jar)
        #domainrequest = s.get(url,headers=headers,verify=False,cookies=jar,proxies=proxies)

        domains = domainrequest.text

        # Turn the HTML into a Beautiful Soup object
        soup = BeautifulSoup(domains, 'lxml')
        
        try:
            table = soup.find("table")
            for row in table.findAll('tr')[1:]:

                # Alternative way to extract domain name
                # domain = row.find('td').find('a').text

                cells = row.findAll("td")

                if len(cells) >= 1:
                    output = ""

                    if keyword:

                        c0 = row.find('td').find('a').text   # domain
                        c1 = cells[1].find(text=True)   # bl
                        c2 = cells[2].find(text=True)   # domainpop
                        c3 = cells[3].find(text=True)   # birth
                        c4 = cells[4].find(text=True)   # Archive.org entries
                        c5 = cells[5].find(text=True)   # similarweb
                        c6 = cells[6].find(text=True)   # similarweb country code
                        c7 = cells[7].find(text=True)   # Dmoz.org
                        c8 = cells[8].find(text=True)   # status com
                        c9 = cells[9].find(text=True)   # status net
                        c10 = cells[10].find(text=True) # status org
                        c11 = cells[11].find(text=True) # status de
                        c12 = cells[12].find(text=True) # tld registered
                        c13 = cells[13].find(text=True) # Related Domains
                        c14 = cells[14].find(text=True) # Domain list
                        c15 = cells[15].find(text=True) # status
                        c16 = cells[16].find(text=True) # related links

                    else:
                        c0 = cells[0].find(text=True)   # domain
                        c1 = cells[1].find(text=True)   # bl
                        c2 = cells[2].find(text=True)   # domainpop
                        c3 = cells[3].find(text=True)   # birth
                        c4 = cells[4].find(text=True)   # Archive.org entries
                        c5 = cells[5].find(text=True)   # similarweb
                        c6 = cells[6].find(text=True)   # similarweb country code
                        c7 = cells[7].find(text=True)   # Dmoz.org
                        c8 = cells[8].find(text=True)   # status com
                        c9 = cells[9].find(text=True)   # status net
                        c10 = cells[10].find(text=True) # status org
                        c11 = cells[11].find(text=True) # status de
                        c12 = cells[12].find(text=True) # tld registered
                        c13 = cells[13].find(text=True) # changes
                        c14 = cells[14].find(text=True) # whois
                        c15 = ""                        # not used
                        c16 = ""                        # not used
                        c17 = ""                        # not used

                        # Expired Domains results have an additional 'Availability' column that breaks parsing "deleted" domains
                        #c15 = cells[15].find(text=True) # related links

                    available = ''
                    if c8 == "available":
                        available += ".com "

                    if c9 == "available":
                        available += ".net "

                    if c10 == "available":
                        available += ".org "

                    if c11 == "available":
                        available += ".de "

                    status = ""
                    if c15:
                        status = c15

                    if (c15 == "Available") and (c0.lower().endswith(".com") or c0.lower().endswith(".net") or c0.lower().endswith(".org")) and (c0 not in maldomainsList):
                        domain_list.append([c0, c3, c4, c15, status, available])

        except Exception as e: 
            #print(e)
            pass
    if len(domain_list) == 0:
        print("[-] No results found for keyword: {0}".format(keyword))
        exit(0)
    else:
        print("Checking " + str(len(domain_list)) + " possible domains for categorization")

        for nested_data in domain_list:

            domain = nested_data[0]
            birthdate = nested_data[1]
            archivedate = nested_data[2]
            availability = nested_data[3]
            currentstatus = nested_data[4]
            d_available = nested_data[5]
            bluecoat = ''
            ibmxforce = ''
            if check == True:
                bluecoat = checkBluecoat(domain)
                print("[+] {}: {}".format(domain, bluecoat))
                ibmxforce = checkIBMXForce(domain)
                print("[+] {}: {}".format(domain, ibmxforce))
                # Sleep to avoid captchas
                doSleep(timing)
            else:
                bluecoat = "skipped"
                ibmxforce = "skipped"
            # Append parsed domain data to list
            data.append([domain,birthdate,archivedate,d_available,currentstatus,bluecoat,ibmxforce])

    # Sort domain list by column 2 (Birth Year)
    sortedData = sorted(data, key=lambda x: x[1], reverse=True) 

    # Build HTML Table
    html = ''
    htmlHeader = '<html><head><title>Expired Domain List</title></head>'
    htmlBody = '<body><p>The following available domains report was generated at {}</p>'.format(timestamp)
    htmlTableHeader = '''
                
                 <table border="1" align="center">
                    <th>Domain</th>
                    <th>Birth</th>
                    <th>Entries</th>
                    <th>TLDs Available</th>
                    <th>Status</th>
                    <th>Symantec</th>
                    <th>Categorization</th>
                    <th>IBM-xForce</th>
                    <th>Categorization</th>
                    <th>WatchGuard</th>
                    <th>Namecheap</th>
                    <th>Archive.org</th>
                 '''

    htmlTableBody = ''
    htmlTableFooter = '</table>'
    htmlFooter = '</body></html>'

    # Build HTML table contents
    for i in sortedData:
        htmlTableBody += '<tr>'
        htmlTableBody += '<td>{}</td>'.format(i[0]) # Domain
        htmlTableBody += '<td>{}</td>'.format(i[1]) # Birth
        htmlTableBody += '<td>{}</td>'.format(i[2]) # Entries
        htmlTableBody += '<td>{}</td>'.format(i[3]) # TLDs
        htmlTableBody += '<td>{}</td>'.format(i[4]) # Status

        htmlTableBody += '<td><a href="https://sitereview.bluecoat.com/sitereview#/?search={}" target="_blank">Bluecoat</a></td>'.format(i[0]) # Bluecoat
        htmlTableBody += '<td>{}</td>'.format(i[5]) # Bluecoat Categorization
        htmlTableBody += '<td><a href="https://exchange.xforce.ibmcloud.com/url/{}" target="_blank">IBM-xForce</a></td>'.format(i[0]) # IBM xForce
        htmlTableBody += '<td>{}</td>'.format(i[6]) # IBM x-Force Categorization
        htmlTableBody += '<td><a href="http://www.borderware.com/domain_lookup.php?ip={}" target="_blank">WatchGuard</a></td>'.format(i[0]) # Borderware WatchGuard
        htmlTableBody += '<td><a href="https://www.namecheap.com/domains/registration/results.aspx?domain={}" target="_blank">Namecheap</a></td>'.format(i[0]) # Namecheap
        htmlTableBody += '<td><a href="http://web.archive.org/web/*/{}" target="_blank">Archive.org</a></td>'.format(i[0]) # Archive.org
        htmlTableBody += '</tr>'

    html = htmlHeader + htmlBody + htmlTableHeader + htmlTableBody + htmlTableFooter + htmlFooter

    logfilename = "{}_domainreport.html".format(timestamp)
    log = open(logfilename,'w')
    log.write(html)
    log.close

    print("\n[*] Search complete")
    print("[*] Log written to {}\n".format(logfilename))
    
    # Print Text Table
    t = Texttable(max_width=maxwidth)
    t.add_rows(sortedData)
    header = ['Domain', 'Birth', '#', 'TLDs', 'Status', 'Symantec', 'IBM']
    t.header(header)
    print(t.draw())
