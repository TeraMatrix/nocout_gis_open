"""
mongo_functions.py
=======================

This file contains the code for mongodb related functions like mongodb insert,mongodb update,mongo_db connection

"""


from nocout_site_name import *
import pymongo
from datetime import datetime
from operator import itemgetter
import imp

utility_module = imp.load_source('utility_functions', '/omd/sites/%s/nocout/utils/utility_functions.py' % nocout_site_name)


def mongo_conn(**kwargs):
	"""
    	Mongodb connection function
	Args: Multiple arguments for connection
	Kwargs: None
	Return : Database object
	
	Raise:
		Exception : PymongoError
    	"""
    	DB = None
    	try:
        	CONN = pymongo.Connection(host=kwargs.get('host'), port=int(kwargs.get('port')))
        	DB = CONN[kwargs.get('db_name')]
    	except pymongo.errors.PyMongoError, e:
       		print 'Error in Mongo Connection'
		print e.message
	return DB


def mongo_db_conn(site_name,db_name):
	"""
    	Mongodb connection main function
	Args: site_name (poller machine site name)
	Kwargs: db_name (database name)
	Return : database object
	
	Raise:
		Exception : PymongoError
    	"""
	db =None
        port = utility_module.db_port(site_name)

        #Get the mongodb connection object
        db = mongo_conn(
                host='localhost',
                port=int(port),
                db_name=db_name
         )
        return db

def mongo_db_insert(db,event_dict,flag):
	"""
    	Mongodb insertion function
	Args: database object
	Kwargs: event_dict (records to be updated),flag (tables to be changed)
	Return : success/failure
	
	Raise:
		Exception : None
    	"""
        success = 0
        failure = 1
        if db:
            if flag == "serv_event":
                db.nocout_service_event_log.insert(event_dict)
                print 'Service Events Entries Inserted'
            elif flag == "host_event":
                db.nocout_host_event_log.insert(event_dict)
                print 'Host Events Entries Inserted'
            elif flag == "snmp_alarm_event":
                db.nocout_snmp_trap_log.insert(event_dict)
            elif flag == "notification_event":
                db.nocout_notification_log.insert(event_dict)
            elif flag == "inventory_services":
                db.nocout_inventory_service_perf_data.insert(event_dict)
            elif flag == "serv_perf_data":
                db.service_perf.insert(event_dict)
            elif flag == "network_perf_data":
                db.network_perf.insert(event_dict)
            elif flag == "status_services":
                db.status_perf.insert(event_dict)
            elif flag == "availability":
                db.device_availability.insert(event_dict)
            elif flag == "kpi_services":
                db.kpi_data.insert(event_dict)
            return success
        else:
                print "Mongo_db insertion failed"
                return failure

def mongo_db_update(db,matching_criteria,event_dict,flag):
	"""
    	Mongodb updation function
	Args: database object
	Kwargs: matching criteria (on which we have to update db),event_dict (records to be updated),flag(which tables to be changed)
	Return : success/failure
	
	Raise:
		Exception : None
    	"""
        success = 0
        failure = 1
        if db:
			try:
				if flag == "inventory_services":
					db.device_inventory_status.update(matching_criteria,event_dict,upsert=True)
				elif flag == "serv_perf_data":
					db.device_service_status.update(matching_criteria,event_dict,upsert=True)
				elif flag == "rad5ktopology":
					db.rad5ktopology.update(matching_criteria,event_dict,upsert=True)
				elif flag == "network_perf_data":
					db.device_network_status.update(matching_criteria,event_dict,upsert=True)
				elif flag == "status_services":
					db.device_status_services_status.update(matching_criteria,event_dict,upsert=True)
				elif flag == "topology":
					db.cambium_topology_data.update(matching_criteria,event_dict,upsert=True)
				elif flag == "wimax_topology":
					db.wimax_topology_data.update(matching_criteria,event_dict,upsert=True)
				elif flag == "kpi_services":
					db.device_kpi_status.update(matching_criteria,event_dict,upsert=True)
				elif flag == 'network_event_status':
					db.network_event_status.update(matching_criteria, event_dict, upsert=True)
				elif flag == 'service_event_status':
				#	print 'Matching Criteria ---'
				#	print matching_criteria
				#	print 'Event  Dict ---'
				#	print event_dict
					db.service_event_status.update(matching_criteria, event_dict, upsert=True)
				elif flag == 'device_first_down':
					db.device_first_down.update(matching_criteria, event_dict, upsert=True)
				return success
			except Exception:
					print "Mongodb updation failed"

				
        else:
                print "Mongo_db updatation failed"
                return failure


def get_latest_entry(db_type=None, db=None, site=None,table_name=None, host=None, serv='_HOST_', ds='rta'):
    """
    	Mongodb latest entry from mysql or mongodb
	Args: database object type
	Kwargs: db (db object) site (site_name),table_name (table in db),host (host_name),serv (service name),ds (data source)
	Return : latest_time
	
	Raise:
		Exception : IndexError
    """
    latest_time = None
    if db_type == 'mongodb':
        if serv == "ping":
		cur = db.network_perf.find({"service": serv, "host": host, "ds":ds}, {"check_time": 1, "ds": 1, "data": 1}).sort("_id", -1).limit(1)
	else:
		cur = db.service_perf.find({"service": serv, "host": host, "ds":ds}, {"check_time": 1, "ds": 1, "data": 1}).sort("_id", -1).limit(1)
	for c in cur:
		entry = c
                data = entry.get('data')
                data = sorted(data, key=itemgetter('time'), reverse=True)
                try:
			latest_time = data[0].get('time')
		except IndexError, e:
			return latest_time
    elif db_type == 'mysql':
        query = "SELECT `check_timestamp` FROM `%s` WHERE" % table_name +\
            " `site_name` = '%s' ORDER BY `id` DESC LIMIT 1" % (site)
        cursor = db.cursor()
        cursor.execute(query)
        entry = cursor.fetchone()
        try:
            latest_time = entry[0]
            latest_time = datetime.fromtimestamp(latest_time)
        except TypeError, e:
            cursor.close()
            return latest_time

        cursor.close()

    return latest_time

