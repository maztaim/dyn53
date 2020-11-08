#!/usr/bin/env python

import requests
import toml
import boto3

config_file = "dynip53.toml"
config = toml.load(config_file)

ip = requests.get(config["url"]).content.decode().strip()
records_list = config["records"]

r53 = boto3.client("route53")


def get_hosted_zone(record):
    zone = r53.list_hosted_zones_by_name(
        DNSName=record.split('.', 1)[1],
        MaxItems="1",
    )
    hosted_zone_name = ".".join(str(zone["HostedZones"][0]["Name"]).rsplit(".")[:-1])
    hosted_zone_id = str(zone["HostedZones"][0]["Id"])
    return {"name": hosted_zone_name, "id": hosted_zone_id}


hosted_zones = [get_hosted_zone(record) for record in records_list]

def get_record(record, hosted_zone):
    check_record_data = r53.list_resource_record_sets(
        HostedZoneId=hosted_zone["id"],
        StartRecordName=record,
        StartRecordType="A",
        MaxItems="1",
    )

    check_record = check_record_data["ResourceRecordSets"][0]["Name"]
    record_value = check_record_data["ResourceRecordSets"][0]["ResourceRecords"][0][
        "Value"
    ]
    full_record = record + "."
    if full_record == check_record and record_value != ip:
        return full_record


records = [
    get_record(record, hosted_zone)
    for record in records_list
    for hosted_zone in hosted_zones
]


def update_record(record, hosted_zone, ip):
    update_record = r53.change_resource_record_sets(
        HostedZoneId=hosted_zone["id"],
        ChangeBatch={
            "Comment": "Updated by dyn53.py.",
            "Changes": [
                {
                    "Action": "UPSERT",
                    "ResourceRecordSet": {
                        "Name": record,
                        "Type": "A",
                        "TTL": 60,
                        "ResourceRecords": [
                            {"Value": ip},
                        ],
                    },
                },
            ],
        },
    )
    return update_record


if not any(record is None for record in records):
    updates = [
        update_record(record, hosted_zone, ip)
        for record in records
        for hosted_zone in hosted_zones
    ]

    print(updates)