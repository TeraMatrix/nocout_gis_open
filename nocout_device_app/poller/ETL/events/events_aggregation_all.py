"""
events_aggregation_all.py
==========================

Script aggregates events data read from historical mysql table
and write to historical mysql table, next in aggregation

Usage ::
python events_aggregation_all.py -t 168 -f weekly -s performance_eventnetworkdaily -d performance_eventnetworkweekly
python events_aggregation_all.py -t 168 -f weekly -s performance_eventservicedaily -d performance_eventserviceweekly
python events_aggregation_all.py -t 720 -f monthly -s performance_eventserviceweekly -d performance_eventservicemonthly
python events_aggregation_all.py -t 8640 -f yearly -s performance_eventserviceyearly -d performance_eventserviceyearly
Options ::
t - Time frame for read operation [Hours]
s - Source Mongodb collection
d - Destination Mysql table
f - Time frame for script viz. daily, hourly etc.
"""

from nocout_site_name import *
import imp
import sys
from datetime import datetime, timedelta
from pprint import pprint
from operator import itemgetter
import optparse
from itertools import groupby


config_mod = imp.load_source('configparser', '/omd/sites/%s/nocout/configparser.py' % nocout_site_name)
mysql_migration_mod = imp.load_source('historical_mysql_export', '/omd/sites/%s/nocout/utils/historical_mysql_export.py' % nocout_site_name)

configs = config_mod.parse_config_obj(historical_conf=True)
desired_site = filter(lambda x: x == nocout_site_name, configs.keys())[0]
desired_config = configs.get(desired_site)

mysql_configs = {
        'host': desired_config.get('ip'),
        'port': int(desired_config.get('sql_port')),
        'user': desired_config.get('user'),
        'password': desired_config.get('sql_passwd'),
        'database': desired_config.get('sql_db')
        }
parser = optparse.OptionParser()
parser.add_option('-s', '--source', dest='source_db', type='str')
parser.add_option('-d', '--destination', dest='destination_db', type='str')
parser.add_option('-t', '--hours', dest='hours', type='choice', choices=['1', '24', '168'])
parser.add_option('-f', '--timeframe', dest='timeframe', type='choice', choices=['hourly', 'daily', 'weekly'])
options, remainder = parser.parse_args(sys.argv[1:])
if options.source_db and options.destination_db and options.hours and options.timeframe:
    source_perf_table=options.source_db
    destination_perf_table=options.destination_db
    hours = int(options.hours)
    time_frame = options.timeframe
else:
    print "Usage: service_mongo_aggregation_hourly.py [options]"
    sys.exit(2)



def prepare_data(aggregated_data_values=[]):
    """
    Events aggregation
    """
    
    data_values = []
    end_time = datetime.now()
    start_time = end_time - timedelta(hours=hours)
    start_time, end_time = start_time - timedelta(minutes=1), end_time + timedelta(minutes=1)
    start_time, end_time = int(start_time.strftime('%s')), int(end_time.strftime('%s'))
    db = mysql_migration_mod.mysql_conn(mysql_configs=mysql_configs)
    if db:
        # Read data from mysql, events historical data
        data_values = mysql_migration_mod.read_data(source_perf_table, db, start_time, end_time)
    data_values = sorted(data_values, key=itemgetter('device_name'))
    print 'Totoal Len'
    print len(data_values)
    for host, host_values in groupby(data_values, key=itemgetter('device_name')):
        aggregated_data_values.extend(quantify_events_data(list(host_values)))

    return aggregated_data_values


def quantify_events_data(host_specific_data):
    host_specific_aggregated_data = []
    #print '## Docs len ##'
    #print len(data_values)
    for index, doc in enumerate(host_specific_data):
        aggr_data = {}
        find_query = {}
        host, ip_address = doc.get('device_name'), doc.get('ip_address')
        ds, service = doc.get('data_source'), doc.get('service_name')
        severity = doc.get('severity')
        current_value = int(doc.get('current_value'))
        site = doc.get('site_name')
        war, cric = doc.get('warning_threshold'), doc.get('critical_threshold')
        check_time = datetime.fromtimestamp(float(doc.get('check_timestamp')))
        original_time = doc.get('sys_timestamp') if doc.get('sys_timestamp') else doc.get('time')
        time = datetime.fromtimestamp(original_time)
        if time_frame == 'daily':
            # Pivot the time to 00:00:00
            time = time.replace(hour=0, minute=0, second=0, microsecond=0)
            # Pivot the time to next day time frame
            time += timedelta(days=1)
        elif time_frame == 'weekly':
            # Pivot the time to 00:00:00
            time = time.replace(hour=23, minute=55, second=0, microsecond=0)
            pivot_to_weekday = 7 - time.weekday()
            # Pivoting the time to Sunday 23:55:00 [end of present week]
            time += timedelta(days=pivot_to_weekday-1)
        elif time_frame == 'monthly':
            # Pivot the time to 23:55:00 of month end
            time = time.replace(month=time.month+1, day=1, hour=23, minute=55,
                    second=0, microsecond=0) - timedelta(days=1)
        elif time_frame == 'yearly':
            # Pivot the time to year end
            time = time.replace(month=12, day=31, hour=23, minute=55,
                    second=0, microsecond=0)
        # Key identifier `original_time` is used in finding next service state change
        aggr_data = {
                'host': host,
                'service': service,
                'ds': ds,
                'severity': severity,
                'time':time,
                'original_time': original_time,
                'site': site,
                'ip_address': ip_address,
                'war': war,
                'cric': cric,
                'check_time': check_time,
                'current_value': current_value
                }
        # Find the entry for next state change of the host service
        state_change_entry = find_next_state_change(aggr_data, host_specific_data[index+1:]) 
        if not state_change_entry or str(state_change_entry[0]['severity']) == str(severity):
            continue
        age_of_state = state_change_entry[0].get('sys_timestamp') - original_time 
        aggr_data.update({
            'min': age_of_state,
            'max': age_of_state,
            'avg': age_of_state
            })

        # Find the existing doc to update
        find_query = {
                #'host': aggr_data.get('host'),
                'service': aggr_data.get('service'),
                'ds': aggr_data.get('ds'),
                'severity': aggr_data.get('severity'),
                #'time': aggr_data.get('time')
                }
        existing_doc, existing_doc_index = find_existing_entry(find_query, host_specific_aggregated_data)
        #print 'existing_doc'
        #print existing_doc
        if existing_doc:
            existing_doc = existing_doc[0]
            max_val = max([aggr_data.get('max'), existing_doc.get('max')])
            min_val = min([aggr_data.get('min'), aggr_data.get('min')])
            avg_val = sum([max_val + min_val])/2.0
            # Update the count for service state
            current_value += int(existing_doc['current_value'])
            aggr_data.update({
                'min': min_val,
                'max': max_val,
                'avg': avg_val,
                'current_value': current_value
                })
            # First remove the existing entry from aggregated_data_values
            host_specific_aggregated_data.pop(existing_doc_index)
        # Add the new aggregated doc to final values
        host_specific_aggregated_data.append(aggr_data)
    
    return host_specific_aggregated_data


def find_next_state_change(aggr_data, host_specific_data):
    intermediate_result = []
    for i in xrange(len(host_specific_data)):
        if set([aggr_data['service'], aggr_data['ds']]) <= set(host_specific_data[i].values()):
            intermediate_result = host_specific_data[i:i+1]
            break
    return intermediate_result
    

def find_existing_entry(find_query, host_specific_aggregated_data):
    """
    Find the doc to upadte
    """
        
    existing_doc = []
    existing_doc_index = None
    find_values = set(find_query.values())
    for i in xrange(len(host_specific_aggregated_data)):
        if find_values <= set(host_specific_aggregated_data[i].values()):
            existing_doc = host_specific_aggregated_data[i:i+1]
            existing_doc_index = i
            break
        #existing = filter(lambda d: set(find_query.values()) <= set(d.values()), aggregated_data_values)
    return existing_doc, existing_doc_index


def usage():
    print "Usage: service_mongo_aggregation_hourly.py [options]"


if __name__ == '__main__':
    final_data_values = prepare_data()
    print '--final_data_values--'
    print len(final_data_values)
    if final_data_values:
        db = mysql_migration_mod.mysql_conn(mysql_configs=mysql_configs)  
        mysql_migration_mod.mysql_export(destination_perf_table, db, final_data_values)
