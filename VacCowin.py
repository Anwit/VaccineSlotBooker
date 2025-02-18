#!/usr/bin/python
# -*- coding: utf-8 -*-

import argparse
import copy
import os
import sys
import time
from types import SimpleNamespace

import requests
from colorama import Fore, Style, init

from utils.appointment import checkAndBook
from utils.displayData import displayInfoDict
from utils.generateOTP import generateTokenOTP
from utils.urls import *
from utils.userInfo import (
    collectUserDetails,
    confirmAndProceed,
    getSavedUserInfo,
    saveUserInfo,
)

init(convert=True)

WARNING_BEEP_DURATION = (1000, 2000)


try:
    import winsound

except ImportError:
    import os

    if sys.platform == "darwin":

        def beep(freq, duration):
            # brew install SoX --> install SOund eXchange universal sound sample translator on mac
            os.system(f"play -n synth {duration/1000} sin {freq} >/dev/null 2>&1")

    else:

        def beep(freq, duration):
            # apt-get install beep  --> install beep package on linux distros before running
            os.system("beep -f %s -l %s" % (freq, duration))


else:

    def beep(freq, duration):
        winsound.Beep(freq, duration)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--token", help="Passing the token directly")
    args = parser.parse_args()

    filename = "vaccine-booking-details.json"
    mobile = None

    print()
    print(f"{Fore.CYAN}", end="")
    print("Running VacCowin...")
    print(f"{Fore.RESET}", end="")
    beep(500, 150)

    try:
        base_request_header = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.95 Safari/537.36",
            "origin": "https://selfregistration.cowin.gov.in",
            "referer": "https://selfregistration.cowin.gov.in/",
        }

        print(
            "\n=================================== IMPORTANT ===================================\n"
        )
        print("This script comes with a automatic OTP fetcher. To enable this feature you need to install \n"
              "SMSForwarder.apk from https://github.com/Anwit/SMSForwarder in your Android Mobile. \n"
              "This App help to fetch CoWin OTP and forward it to specified email. This script will then fetch \n"
              "the OTP from your email. Without this feature you need to enter the OTP manually every 15 mins \n"
              "(default timeout for CoWin OTP)\n")
        try_file = input("\nDo you want to enable autoOTPCapture feature? (y/n Default n): ")
        try_file = try_file if try_file else "n"
        
        email = ''
        password = ''
        if try_file == "y":
            email = input("\nEnter email id from where you want to fetch the OTP: ")
            password = input("\nEnter password: ")
            autoOTPCapture = True
        elif try_file == "n":
            autoOTPCapture = False
        else:
            print("\nInvalid input. Not enabling autoOTPCapture feature.\n")
            autoOTPCapture = False

        if args.token:
            token = args.token
        else:
            print(f"{Fore.YELLOW}", end="")
            mobile = input("Enter the Registered Mobile Number: ")
            print(f"{Fore.RESET}", end="")
            token = generateTokenOTP(mobile, base_request_header, autoOTPCapture, email, password)

        request_header = copy.deepcopy(base_request_header)
        request_header["Authorization"] = f"Bearer {token}"

        if os.path.exists(filename):
            print(f"{Fore.RESET}", end="")
            print(
                "\n=================================== Note ===================================\n"
            )
            print(f"{Fore.GREEN}", end="")
            print(
                f"Information from a Previous Session already exists in {filename} in this directory."
            )
            print(f"{Fore.CYAN}", end="")
            print(
                f"IMPORTANT: If you're running this application for the first time then we recommend NOT To USE THE FILE!\n"
            )
            print(f"{Fore.YELLOW}", end="")
            try_file = input(
                "Would you like to see the details from that file and confirm to proceed? (y/n Default y): "
            )
            print(f"{Fore.RESET}", end="")
            try_file = try_file if try_file else "y"

            if try_file == "y":
                print(f"{Fore.RESET}", end="")
                collected_details = getSavedUserInfo(filename)
                print(
                    "\n================================= Info =================================\n"
                )
                displayInfoDict(collected_details)

                print(f"{Fore.YELLOW}", end="")
                file_acceptable = input(
                    "\nProceed with the above Information? (y/n Default n): "
                )
                print(f"{Fore.RESET}", end="")
                file_acceptable = file_acceptable if file_acceptable else "n"

                if file_acceptable != "y":
                    collected_details = collectUserDetails(request_header)
                    saveUserInfo(filename, collected_details)

            else:
                collected_details = collectUserDetails(request_header)
                saveUserInfo(filename, collected_details)

        else:
            collected_details = collectUserDetails(request_header)
            saveUserInfo(filename, collected_details)
            confirmAndProceed(collected_details)

        info = SimpleNamespace(**collected_details)

        token_valid = True
        while token_valid:
            request_header = copy.deepcopy(base_request_header)
            request_header["Authorization"] = f"Bearer {token}"

            # call function to check and book slots
            token_valid = checkAndBook(
                request_header,
                info.beneficiary_dtls,
                info.location_dtls,
                info.search_option,
                min_slots=info.minimum_slots,
                ref_freq=info.refresh_freq,
                auto_book=info.auto_book,
                start_date=info.start_date,
                vaccine_type=info.vaccine_type,
                fee_type=info.fee_type,
            )

            # check if token is still valid
            beneficiaries_list = requests.get(BENEFICIARIES_URL, headers=request_header)
            if beneficiaries_list.status_code == 200:
                token_valid = True

            else:
                # if token invalid, regenerate OTP and new token
                beep(WARNING_BEEP_DURATION[0], WARNING_BEEP_DURATION[1])
                print(f"{Fore.RED}", end="")
                print("\n\nToken is INVALID!")
                print(f"{Fore.RESET}", end="")
                token_valid = False

                if autoOTPCapture:
                    print("\nTrying to fetch another OTP....")
                    token = generateTokenOTP(mobile, base_request_header, autoOTPCapture, email, password)
                    token_valid = True
                else:
                    print(f"{Fore.YELLOW}", end="")
                    tryOTP = input("Do you want to try for a new Token? (y/n Default y): ")
                    for i in range(1, 0, -1):
                        print(f"{Fore.RED}", end="")
                        msg = f"Wait for {i} seconds.."
                        print(msg, end="\r", flush=True)
                        print(f"{Fore.RESET}", end="")
                        sys.stdout.flush()
                        time.sleep(1)
                    if tryOTP.lower() == "y" or not tryOTP:
                        if not mobile:
                            print(f"{Fore.YELLOW}", end="")
                            mobile = input("Enter the Registered Mobile Number: ")
                        token = generateTokenOTP(mobile, base_request_header, autoOTPCapture, email, password)
                        token_valid = True
                    else:
                        print(f"{Fore.RED}", end="")
                        print("Exiting the Script...")
                        os.system("pause")
                        print(f"{Fore.RESET}", end="")

    except Exception as e:
        print(f"{Fore.RED}", end="")
        print(str(e))
        print("Exiting the Script...")
        os.system("pause")
        print(f"{Fore.RESET}", end="")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n\n{Fore.RED}User Aborted the Program.\nExiting, Please Wait...")
        sys.exit()
