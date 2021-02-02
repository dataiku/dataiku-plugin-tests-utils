#!/usr/bin/env python

import copy
import json
import os
import re
import sys

import requests


def send_slack_signal(path_to_raw_daily, slack_endpoint):

    block_PR_template = [
        {
          "type": "divider"
        },
        {
          "type": "section",
          "text": {
            "type": "mrkdwn",
            "text": "<{PR_github}|{plugin_name}> | {plugin_PR} | {PR_creator} ",
          }
        }
    ]

    block_branch_template = [
        {
          "type": "divider"
        },
        {
          "type": "section",
          "text": {
            "type": "mrkdwn",
            "text": "<{branch_github}|{plugin_name}> | {plugin_branch}",
          }
        }
    ]

    section_template = {
      "type": "section",
      "text": {
        "type": "mrkdwn",
        "text": ""
      }
    }

    payload_base = {
      "blocks": []
    }

    block = None
    blocks = []

    all_status_files = [f for f in os.listdir(path_to_raw_daily)]

    for status_file in all_status_files:
        success_counter = 0
        failure_counter = 0
        unstable_counter = 0
        last_success_url = ""
        last_failure_url = ""
        last_unstable_url = ""
        PR_title = ""
        PR_author = ""
        PR_github_link = ""
        branch_name = ""

        print("Parsing file [{}] --------- ".format(os.path.join(path_to_raw_daily, status_file)))

        with open(os.path.join(path_to_raw_daily, status_file)) as fd:
            content = fd.readlines()

        print("Content---")
        print(content)
        print("----------")
        for index in range(len(content)):
            content[index] = content[index].strip().split(';')
            if content[index][5] == "SUCCESS":
                success_counter += 1
                last_success_url = "{}/allure".format(content[index][0])
            elif content[index][5] == "UNSTABLE":
                unstable_counter += 1
                last_unstable_url = "{}/allure".format(content[index][0])
            else:
                failure_counter += 1
                last_failure_url = "{}/allure".format(content[index][0])
            PR_title = content[index][1]
            PR_author = content[index][2]
            PR_github_link = content[index][3]
            branch_name = content[index][4]

        section = copy.deepcopy(section_template)
        section_text_line = ""
        if success_counter > 0:
            section_text_line = section_text_line + "\n\n" if len(section_text_line) > 0 else section_text_line
            section_text_line += ":successful: <{last_success_link}|Daily success>: {daily_success}".format(daily_success=success_counter, last_success_link=last_success_url)
        if unstable_counter > 0:
            section_text_line = section_text_line + "\n\n" if len(section_text_line) > 0 else section_text_line
            section_text_line += ":warning: <{last_unstable_link}|Daily unstable>: {daily_unstable}".format(daily_unstable=unstable_counter, last_unstable_link=last_unstable_url)
        if failure_counter > 0:
            section_text_line = section_text_line + "\n\n" if len(section_text_line) > 0 else section_text_line
            section_text_line += ":failed: <{last_failure_link}|Daily failure>: {daily_failure}".format(daily_failure=failure_counter, last_failure_link=last_failure_url)

        section["text"]["text"] = section_text_line
        print("section ---")
        print(json.dumps(section, indent=2))
        print("----------")

        plugin_url = last_success_url if last_success_url != "" else last_failure_url
        plugin_url = plugin_url if plugin_url != "" else last_unstable_url

        ret = re.match(".*/Dataiku/job/(.+)/job/.*", plugin_url)
        plugin_name = ret.group(1)
        
        if PR_title == 'null' and PR_author == 'null' and PR_github_link == 'null':
            block = copy.deepcopy(block_branch_template)
            github_link = "https://github.com/dataiku/{plugin_name}/tree/{branch_name}".format(plugin_name=plugin_name,
                                                                                              branch_name=branch_name)
            block[1]["text"]["text"] = block[1]["text"]["text"].format(plugin_name=plugin_name,plugin_branch=branch_name,
                                                                      branch_github=github_link)
        else:
            block = copy.deepcopy(block_PR_template)
            block[1]["text"]["text"] = block[1]["text"]["text"].format(plugin_name=plugin_name, plugin_PR=PR_title, PR_creator=PR_author,
                                                                      PR_github=PR_github_link)
        block.append(section)
        blocks.extend(block)
        print("block ---")
        print(json.dumps(block, indent=2))
        print("---------")

    print("blocks ---")
    print(json.dumps(blocks, indent=2))
    print("---------")

    if blocks:
        payload_base["blocks"].extend(blocks)

        print("payload ----")
        print(json.dumps(payload_base, indent=2))
        print("------------")

        x = requests.post(slack_endpoint, data=json.dumps(payload_base))
        x.raise_for_status()

    # TODO: Re instate that once the bugs are fixed
    #    for status_file in all_status_files:
    #        os.remove(os.path.join(path, status_file))
    else:
        print("Nothing to notify, exiting ...")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("usage: {app} <path to raw daily report> <slack endpoint>".format(app=sys.argv[0]))
        sys.exit(1)

    print("ARGV ---")
    print(sys.argv[1])
    print(sys.argv[2])
    print("---------")
    send_slack_signal(sys.argv[1], sys.argv[2])