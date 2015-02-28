from celery import task, group

from django.db.models import Q, Count, F
from django.utils import timezone
import datetime

# nocout project settings # TODO: Remove the HARDCODED technology IDs
from nocout.settings import PMP, WiMAX, TCLPOP

from organization.models import Organization
from device.models import DeviceTechnology, Device
from capacity_management.models import SectorCapacityStatus, BackhaulCapacityStatus
from performance.models import Topology, NetworkStatus, ServiceStatus
from dashboard.models import (DashboardSetting, DashboardSeverityStatusTimely, DashboardSeverityStatusHourly,
        DashboardSeverityStatusDaily, DashboardSeverityStatusWeekly, DashboardSeverityStatusMonthly,
        DashboardSeverityStatusYearly, DashboardRangeStatusTimely, DashboardRangeStatusHourly, DashboardRangeStatusDaily,
        DashboardRangeStatusWeekly, DashboardRangeStatusMonthly, DashboardRangeStatusYearly,
    )

from inventory.utils.util import organization_sectors, organization_network_devices
from inventory.models import get_default_org

from inventory.tasks import bulk_update_create

from dashboard.utils import \
    get_topology_status_results, \
    get_dashboard_status_range_counter, \
    get_dashboard_status_range_mapped


import logging
logger = logging.getLogger(__name__)


@task()
def calculate_speedometer_dashboards():
    """

    :return: Calculation Status for the objects
    """
    g_jobs = list()

    user_organizations = Organization.objects.all()
    processed_for = timezone.now()

    for organization in user_organizations:
        g_jobs.append(
            calculate_timely_latency.s(
                organization=organization,
                dashboard_name='latency-network',
                processed_for=processed_for
            )
        )

        g_jobs.append(
            calculate_timely_packet_drop.s(
                organization=organization,
                dashboard_name='packetloss-network',
                processed_for=processed_for
            )
        )

        g_jobs.append(
            calculate_timely_down_status.s(
                organization=organization,
                dashboard_name='down-network',
                processed_for=processed_for
            )
        )

        temperatures = ['IDU', 'ACB', 'FAN']

        for temp in temperatures:
            g_jobs.append(
                calculate_timely_temperature.s(
                    organization=organization,
                    processed_for=processed_for,
                    chart_type=temp
                )
            )

    job = group(g_jobs)
    result = job.apply_async()
    ret = False

    for r in result.get():
        ret |= r

    return ret


@task()
def calculate_status_dashboards(technology):
    """

    :return:
    """
    g_jobs = list()
    ret = False

    user_organizations = Organization.objects.all()
    processed_for = timezone.now()

    dashboards = [
        "latency-{0}".format(technology),
        "packetloss-{0}".format(technology),
        "down-{0}".format(technology),
    ]

    for dashboard in dashboards:
        for organization in user_organizations:
            g_jobs.append(
                calculate_timely_latency.s(
                    organization=organization,
                    dashboard_name=dashboard,
                    processed_for=processed_for,
                    technology=technology
                )
            )

    if len(g_jobs):
        job = group(g_jobs)
        result = job.apply_async()
        for r in result.get():
            ret |= r
    return ret


@task()
def calculate_range_dashboards():
    """

    :return:
    """
    g_jobs = list()
    ret = False

    user_organizations = Organization.objects.all()
    processed_for = timezone.now()

    sector_tech = ['PMP', 'WiMAX']
    backhaul_tech = ['TCLPOP', 'PMP', 'WiMAX']

    for tech in sector_tech:
        g_jobs.append(
            calculate_timely_sector_capacity.s(
                user_organizations,
                technology=tech,
                model=DashboardSeverityStatusTimely,
                processed_for=processed_for
            )
        )

        g_jobs.append(
            calculate_timely_sales_opportunity.s(
                user_organizations,
                technology=tech,
                model=DashboardSeverityStatusTimely,
                processed_for=processed_for
            )
        )

    for tech in backhaul_tech:
        g_jobs.append(
            calculate_timely_backhaul_capacity.s(
                user_organizations,
                technology=tech,
                model=DashboardSeverityStatusTimely,
                processed_for=processed_for
            )
        )

    if len(g_jobs):
        job = group(g_jobs)
        result = job.apply_async()
        for r in result.get():
            ret |= r

    return ret


@task()
def calculate_timely_sector_capacity(organizations, technology, model, processed_for):
    '''
    :param technology: Named Tuple
    :param model: Dashboard Model to store timely dashboard data.
    :param processed_for:
    return
    '''
    try:
        sector_technology = eval(technology)
    except Exception as e:
        logger.exception(e)
        return False

    required_values = [
        'id',
        'sector__name',
        'sector__sector_configured_on__device_name',
        'severity',
        'sys_timestamp',
        'age',
        'organization'
    ]

    dashboard_name = '%s_sector_capacity' % (sector_technology.NAME.lower())

    sectors = SectorCapacityStatus.objects.filter(
            Q(organization__in=organizations),
            Q(sector__sector_configured_on__device_technology=sector_technology.ID),
            Q(severity__in=['warning', 'critical', 'ok', 'unknown']),
        ).values(*required_values)

    bulk_data_list = list()

    for item in sectors:
        # Create the range_counter dictionay containg the model's field name as key
        range_counter = dict(
            dashboard_name=dashboard_name,
            device_name=item['sector__sector_configured_on__device_name'],
            reference_name=item['sector__name'],
            processed_for=processed_for,
            organization=item['organization']
        )
        # Update the range_counter on the basis of severity.
        if (item['age'] <= item['sys_timestamp'] - 600) and (item['severity'].strip().lower() in ['warning', 'critical']):
            range_counter.update({item['severity'].strip().lower() : 1})
        elif item['severity'].strip().lower() == 'ok':
            range_counter.update({'ok' : 1})
        else:
            range_counter.update({'unknown' : 1})

        bulk_data_list.append(model(**range_counter))

    if len(bulk_data_list):
        # call the method to bulk create the onjects.
        bulk_update_create.delay(bulky=bulk_data_list,
                             action='create',
                             model=model)
    return True


@task()
def calculate_timely_backhaul_capacity(organizations, technology, model, processed_for):
    '''
    :param technology: Named Tuple
    :param model: Dashboard Model to store timely dashboard data.
    :param processed_for:
    return
    '''
    try:
        backhaul_technology = eval(technology)
    except Exception, e:
        return False

    dashboard_name = '%s_backhaul_capacity' % (backhaul_technology.NAME.lower())

    required_values = [
        'id',
        'backhaul__name',
        'backhaul__bh_configured_on__device_name',
        'severity',
        'sys_timestamp',
        'age',
        'organization'
    ]

    backhaul = BackhaulCapacityStatus.objects.filter(
            Q(organization__in=organizations),
            Q(backhaul__bh_configured_on__device_technology=backhaul_technology.ID),
            Q(severity__in=['warning', 'critical', 'ok', 'unknown']),
        ).values(*required_values)

    data_list = list()
    for item in backhaul:
        # Create the range_counter dictionay containg the model's field name as key
        range_counter = dict(
            dashboard_name=dashboard_name,
            device_name=item['backhaul__bh_configured_on__device_name'],
            reference_name=item['backhaul__name'],
            processed_for=processed_for,
            organization=item['organization']
        )
        # Update the range_counter on the basis of severity.
        if (item['age'] <= item['sys_timestamp'] - 600) and (item['severity'].strip().lower() in ['warning', 'critical']):
            range_counter.update({item['severity'].strip().lower() : 1})
        elif item['severity'].strip().lower() == 'ok':
            range_counter.update({'ok' : 1})
        else:
            range_counter.update({'unknown' : 1})

        # Create the list of model object.
        try:
            data_list.append(model(**range_counter))
        except Exception as e:
            pass

    # call the method to bulk create the onjects.
    bulk_update_create.delay(data_list, action='create', model=model)
    return True


@task()
def calculate_timely_sales_opportunity(organizations, technology, model, processed_for):
    '''
    :param technology: Named Tuple
    :param model: Dashboard Model to store timely dashboard data.
    :param processed_for: datetime (example: timezone.now())
    return
    '''
    try:
        sales_technology = eval(technology)
    except Exception, e:
        return False
    # convert the data source in format topology_pmp/topology_wimax
    data_source = '%s-%s' % ('topology', sales_technology.NAME.lower())
    dashboard_name = '%s_sales_opportunity' % (sales_technology.NAME.lower())

    technology_id = sales_technology.ID if sales_technology else None
    try:
        dashboard_setting = DashboardSetting.objects.get(technology_id=technology_id,
                                                         page_name='main_dashboard',
                                                         name=data_source,
                                                         is_bh=False)
    except DashboardSetting.DoesNotExist as e:
        logger.info("DashboardSetting for %s is not available." % dashboard_name)
        return False

    # get the sector of User's Organization [and Sub Organization]
    user_sector = organization_sectors(organizations, technology_id)
    # get the device of the user sector.
    # sector_devices = Device.objects.filter(id__in=user_sector.values_list('sector_configured_on', flat=True))

    # get the list of dictionary on the basis of parameters.
    service_status_results = get_topology_status_results(
        user_devices=None,
        model=Topology,
        service_name=None,
        data_source='topology',
        user_sector=user_sector
    )

    data_list = list()
    for result in service_status_results:
        # get the dictionary containing the model's field name as key.
        # range_counter in format {'range1': 1, 'range2': 2,...}
        range_counter = get_dashboard_status_range_counter(dashboard_setting, [result])
        # update the range_counter to add further details
        range_counter.update(
            {
                'dashboard_name': dashboard_name,
                'device_name': result['device_name'],
                'reference_name': result['name'],   # Store sector name as reference_name
                'processed_for': processed_for,
                'organization': result['organization']
            }
        )

        # prepare a list of model object.
        data_list.append(model(**range_counter))

    # call method to bulk create the model object.
    bulk_update_create.delay(data_list, action='create', model=model)
    return True


@task()
def calculate_timely_latency(organization, dashboard_name, processed_for ,technology=None):
    '''
    Method to calculate the latency status of devices.

    :param:
    organizations: list of organization.
    dashboard_name: name of dashboard used in dashboard_setting.
    processed_for: datetime.
    technology: Named Tuple.

    return:
    '''
    try:
        latency_technology = eval(technology)
        processed_for = processed_for
        technology_id = latency_technology.ID
    except Exception as e:
        logger.exception(e)
        return False

    g_jobs = list()
    ret = False

    #calculate these organization wise

    # get the device of user's organization [and sub organization]
    sector_devices = organization_network_devices(organization, technology_id)

    if sector_devices.count():
        # get the list of dictionay where 'machine__name' and 'device_name' as key of the user's device.
        sector_devices = sector_devices.filter(sector_configured_on__isnull=False).values('machine__name', 'device_name')

        # get the dictionary of machine_name as key and device_name as a list for that machine.
        machine_dict = prepare_machines(sector_devices)

        status_count = 0

        # creating a list dictionary using machine name and there corresponing device list.
        for machine_name, device_list in machine_dict.items():
            status_count += NetworkStatus.objects.order_by().filter(
                device_name__in=device_list,
                service_name='ping',
                data_source='rta',
                current_value__gt=0,
                severity__in=['warning', 'critical', 'down']
                ).using(machine_name).count()

        g_jobs.append(
            calculate_timely_network_alert.s(
                dashboard_name=dashboard_name,
                processed_for=processed_for,
                organization=organization,
                technology=technology,
                status_count=status_count,
                status_dashboard_name=None
            )
        )

    if len(g_jobs):
        job = group(g_jobs)
        result = job.apply_async()
        for r in result.get():
            ret |= r

    return ret



@task()
def calculate_timely_packet_drop(organization, dashboard_name, processed_for, technology=None):
    '''
    Method to calculate the packed drop status of devices.

    :param:
    organizations: list of organization.
    dashboard_name: name of dashboard used in dashboard_setting.
    processed_for: datetime.
    technology: Named Tuple.

    return:
    '''
    try:
        latency_technology = eval(technology)
        processed_for = processed_for
        technology_id = latency_technology.ID
    except Exception as e:
        logger.exception(e)
        return False

    g_jobs = list()
    ret = False

    #calculate these organization wise

    # get the device of user's organization [and sub organization]
    sector_devices = organization_network_devices(organization, technology_id)

    if sector_devices.count():
        # get the list of dictionay where 'machine__name' and 'device_name' as key of the user's device.
        sector_devices = sector_devices.filter(sector_configured_on__isnull=False).values('machine__name', 'device_name')

        # get the dictionary of machine_name as key and device_name as a list for that machine.
        machine_dict = prepare_machines(sector_devices)

        status_count = 0

        # creating a list dictionary using machine name and there corresponing device list.
        for machine_name, device_list in machine_dict.items():
            status_count += NetworkStatus.objects.order_by().filter(
                device_name__in=device_list,
                service_name='ping',
                data_source='pl',
                current_value__lt=100,
                severity__in=['warning', 'critical', 'down']
                ).using(machine_name).count()

        g_jobs.append(
            calculate_timely_network_alert.s(
                dashboard_name=dashboard_name,
                processed_for=processed_for,
                organization=organization,
                technology=technology,
                status_count=status_count,
                status_dashboard_name=None
            )
        )

    if len(g_jobs):
        job = group(g_jobs)
        result = job.apply_async()
        for r in result.get():
            ret |= r

    return ret



@task()
def calculate_timely_down_status(organization, dashboard_name, processed_for, technology=None):
    '''
    Method to calculate the packed drop status of devices.

    :param:
    organizations: list of organization.
    dashboard_name: name of dashboard used in dashboard_setting.
    processed_for: datetime.
    technology: Named Tuple.

    return:
    '''
    try:
        latency_technology = eval(technology)
        processed_for = processed_for
        technology_id = latency_technology.ID
    except Exception as e:
        logger.exception(e)
        return False

    g_jobs = list()
    ret = False

    #calculate these organization wise

    # get the device of user's organization [and sub organization]
    sector_devices = organization_network_devices(organization, technology_id)

    if sector_devices.count():
        # get the list of dictionay where 'machine__name' and 'device_name' as key of the user's device.
        sector_devices = sector_devices.filter(sector_configured_on__isnull=False).values('machine__name', 'device_name')

        # get the dictionary of machine_name as key and device_name as a list for that machine.
        machine_dict = prepare_machines(sector_devices)

        status_count = 0

        # creating a list dictionary using machine name and there corresponing device list.
        for machine_name, device_list in machine_dict.items():
            status_count += NetworkStatus.objects.order_by().filter(
                device_name__in=device_list,
                service_name='ping',
                data_source='rta',
                current_value__gte=100,
                severity__in=['critical', 'down']
                ).using(machine_name).count()

        g_jobs.append(
            calculate_timely_network_alert.s(
                dashboard_name=dashboard_name,
                processed_for=processed_for,
                organization=organization,
                technology=technology,
                status_count=status_count,
                status_dashboard_name=None
            )
        )

    if len(g_jobs):
        job = group(g_jobs)
        result = job.apply_async()
        for r in result.get():
            ret |= r

    return ret



@task()
def calculate_timely_temperature(organization, processed_for, chart_type='IDU'):
    '''
    Method to calculate the temperature status of devices.

    :param:
    organizations: list of organization.
    processed_for: datetime.
    chart_type: string.

    return:
    '''

    if chart_type == 'IDU':
        service_list = ['wimax_bs_temperature_acb', 'wimax_bs_temperature_fan']
        data_source_list = ['acb_temp', 'fan_temp']
    elif chart_type == 'ACB':
        service_list = ['wimax_bs_temperature_acb']
        data_source_list = ['acb_temp']
    elif chart_type == 'FAN':
        service_list = ['wimax_bs_temperature_fan']
        data_source_list = ['fan_temp']
    else:
        return False

    g_jobs = list()
    ret = False

    technology_id = 3
    processed_for=processed_for

    status_dashboard_name = 'temperature-' + chart_type.lower()

    # get the device of user's organization [and sub organization]
    sector_devices = organization_network_devices(organization, technology_id)

    if sector_devices.count():
        # get the list of dictionay where 'machine__name' and 'device_name' as key of the user's device.
        sector_devices = sector_devices.filter(sector_configured_on__isnull=False).values('machine__name', 'device_name')

        machine_dict = prepare_machines(sector_devices)

        # count of devices in severity
        status_count = 0
        # creating a list dictionary using machine name and there corresponing device list.
        # And list is order by device_name.
        for machine_name, device_list in machine_dict.items():
            status_count += ServiceStatus.objects.order_by().filter(
                device_name__in=device_list,
                service_name__in=service_list,
                data_source__in=data_source_list,
                severity__in=['warning', 'critical']
                ).count().using(machine_name)

        g_jobs.append(
            calculate_timely_network_alert.s(
                dashboard_name='temperature',
                processed_for=processed_for,
                organization=organization,
                technology='WiMAX',
                status_count=status_count,
                status_dashboard_name=status_dashboard_name
            )
        )

    if len(g_jobs):
        job = group(g_jobs)
        result = job.apply_async()
        for r in result.get():
            ret |= r

    return ret


@task()
def calculate_timely_network_alert(dashboard_name,
                                   processed_for,
                                   organization,  # assume the organization to be default
                                   technology=None,
                                   status_count=0,
                                   status_dashboard_name=None
                                   ):
    """
    prepare a list of model object to bulk create the model objects.

    :param dashboard_name: dashboard_name: name of dashboard used in dashboard_setting.
    :param processed_for: processed_for: datetime
    :param technology: technology: Named Tuple
    :param status_count: count of status of objects in warning, critical
    :param status_dashboard_name: string
    return: True
    """
    if not organization:
        assumed_organization = get_default_org()

    try:
        if technology:
            network_technology = eval(technology)
        else:
            network_technology = None
    except Exception as e:
        logger.exception(e)
        return False

    technology_id = network_technology.ID if network_technology else None
    try:
        dashboard_setting = DashboardSetting.objects.get(
            technology_id=technology_id,
            page_name='main_dashboard',
            name=dashboard_name,
            is_bh=False
        )
    except DashboardSetting.DoesNotExist as e:
        logger.exception(" Dashboard Setting of {0} is not available. {1}".format(dashboard_name, e))
        return False

    device_name = '-1'  # lets just say it does not exists # todo remove this s**t
    processed_for = processed_for

    bulky = list()

    if status_dashboard_name is None:
        status_dashboard_name = dashboard_name

    # get the dictionay where keys are same as of the model fields.
    dashboard_data_dict = get_dashboard_status_range_mapped(dashboard_setting, status_count)
    # updating the dictionay with some other fields used in model.

    if dashboard_data_dict:
        dashboard_data_dict.update(
            {
                'device_name': device_name,
                'reference_name': device_name,
                'dashboard_name': status_dashboard_name,
                'processed_for': processed_for,
                'organization': assumed_organization
            }
        )
        # creating a list of model object for bulk create.
        bulky.append(DashboardRangeStatusTimely(**dashboard_data_dict))

        # call celery task to create dashboard data
        bulk_update_create.delay(bulky=bulky,
                                 action='create',
                                 model=DashboardRangeStatusTimely)

    return True


def prepare_machines(device_list):
    """
    Create a dictionay machine as a key and device_name as a list for that machine.

    :param:
    device_list: list of devices.

    return: dictionay.
    """
    # Unique machine from the device_list
    unique_device_machine_list = {device['machine__name']: True for device in device_list}.keys()

    machine_dict = {}
    # Creating the machine as a key and device_name as a list for that machine.
    for machine in unique_device_machine_list:
        machine_dict[machine] = [device['device_name'] for device in device_list if
                                 device['machine__name'] == machine]

    return machine_dict


@task()
def calculate_hourly_main_dashboard():
    '''
    Task to calculate the main dashboard status in every hour using celerybeat.
    '''

    now = timezone.now()
    calculate_hourly_severity_status(now)
    calculate_hourly_range_status(now)


def calculate_hourly_severity_status(now):
    '''
    Calculate the status of dashboard from DashboardSeverityStatusTimely model
    and create list of DashboardSeverityStatusHourly model object for calculated data
    and then delete all data from the DashboardSeverityStatusTimely model.

    :param now: datetime (example: timezone.now())

    return:
    '''
    # get all data from the model order by 'dashboard_name' and 'device_name'.
    last_hour_timely_severity_status = DashboardSeverityStatusTimely.objects.order_by('dashboard_name',
            'device_name').filter(processed_for__lt=now)

    hourly_severity_status_list = []    # list for the DashboardSeverityStatusHourly model object
    hourly_severity_status = None
    dashboard_name = ''
    device_name = ''

    for timely_severity_status in last_hour_timely_severity_status:
        # Sum the status value for the same dashboard_name and device_name.
        if dashboard_name == timely_severity_status.dashboard_name and device_name == timely_severity_status.device_name:
            hourly_severity_status = sum_severity_status(hourly_severity_status, timely_severity_status)
        else:
            # Create new model object when dashboard_name and device_name are different from previous dashboard_name and device_name.
            hourly_severity_status = DashboardSeverityStatusHourly(
                dashboard_name=timely_severity_status.dashboard_name,
                device_name=timely_severity_status.device_name,
                reference_name=timely_severity_status.reference_name,
                processed_for=now,
                warning=timely_severity_status.warning,
                critical=timely_severity_status.critical,
                ok=timely_severity_status.ok,
                down=timely_severity_status.down,
                unknown=timely_severity_status.unknown
            )
            # append in list for every new dashboard_name and device_name.
            hourly_severity_status_list.append(hourly_severity_status)
            # assign new dashboard_name and device_name.
            dashboard_name = timely_severity_status.dashboard_name
            device_name = timely_severity_status.device_name

    bulk_update_create.delay(hourly_severity_status_list, action='create', model=DashboardSeverityStatusHourly)

    # delete the data from the DashboardSeverityStatusTimely model.
    last_hour_timely_severity_status.delete()


def calculate_hourly_range_status(now):
    '''
    Calculate the status of dashboard from DashboardRangeStatusTimely model
    and create list of DashboardRangeStatusHourly model object for calculated data
    and then delete all data from the DashboardRangeStatusTimely model.

    :param now: datetime (example: timezone.now())

    return:
    '''
    # get all data from the model order by 'dashboard_name' and 'device_name'.
    last_hour_timely_range_status = DashboardRangeStatusTimely.objects.order_by('dashboard_name',
            'device_name').filter(processed_for__lt=now)

    hourly_range_status_list = []   # list for the DashboardRangeStatusHourly model object
    hourly_range_status = None
    dashboard_name = ''
    device_name = ''
    for timely_range_status in last_hour_timely_range_status:
        # Sum the status value for the same dashboard_name and device_name.
        if dashboard_name == timely_range_status.dashboard_name and device_name == timely_range_status.device_name:
            hourly_range_status = sum_range_status(hourly_range_status, timely_range_status)
        else:
            # Create new model object when dashboard_name and device_name are different from previous dashboard_name and device_name.
            hourly_range_status = DashboardRangeStatusHourly(
                dashboard_name=timely_range_status.dashboard_name,
                device_name=timely_range_status.device_name,
                reference_name=timely_range_status.reference_name,
                processed_for=now,
                range1=timely_range_status.range1,
                range2=timely_range_status.range2,
                range3=timely_range_status.range3,
                range4=timely_range_status.range4,
                range5=timely_range_status.range5,
                range6=timely_range_status.range6,
                range7=timely_range_status.range7,
                range8=timely_range_status.range8,
                range9=timely_range_status.range9,
                range10=timely_range_status.range10,
                unknown=timely_range_status.unknown
            )
            # append in list for every new dashboard_name and device_name.
            hourly_range_status_list.append(hourly_range_status)
            # assign new dashboard_name and device_name.
            dashboard_name = timely_range_status.dashboard_name
            device_name = timely_range_status.device_name

    bulk_update_create.delay(hourly_range_status_list, action='create', model=DashboardRangeStatusHourly)

    # delete the data from the DashboardRangeStatusTimely model.
    last_hour_timely_range_status.delete()


def sum_severity_status(parent, child):
    parent.warning += child.warning
    parent.critical += child.critical
    parent.ok += child.ok
    parent.down += child.down
    parent.unknown += child.unknown

    return parent


def sum_range_status(parent, child):
    parent.range1 += child.range1
    parent.range2 += child.range2
    parent.range3 += child.range3
    parent.range4 += child.range4
    parent.range5 += child.range5
    parent.range6 += child.range6
    parent.range7 += child.range7
    parent.range8 += child.range8
    parent.range9 += child.range9
    parent.range10 += child.range10
    parent.unknown += child.unknown

    return parent


@task()
def calculate_daily_main_dashboard():
    '''
    Task to calculate the daily status of main dashboard.
    '''
    now = timezone.now()
    calculate_daily_severity_status(now)
    calculate_daily_range_status(now)


def calculate_daily_severity_status(now):
    '''
    Calculate the status of dashboard from DashboardSeverityStatusHourly model
    and create list of DashboardSeverityStatusDaily model object for calculated data
    and then delete all data from the DashboardSeverityStatusHourly model.

    :param now: datetime (example: timezone.now())

    return:
    '''
    # get the current timezone.
    tzinfo = timezone.get_current_timezone()
    # get today date according to current timezone and reset time to 12 o'clock.
    today = timezone.datetime(now.year, now.month, now.day, tzinfo=tzinfo)
    previous_day = now - timezone.timedelta(days=1)
    yesterday = timezone.datetime(previous_day.year, previous_day.month, previous_day.day, tzinfo=tzinfo)
    # get all result of yesterday only and order by 'dashboard_name' and'device_name'
    last_day_timely_severity_status = DashboardSeverityStatusHourly.objects.order_by('dashboard_name',
            'device_name').filter(processed_for__gte=yesterday, processed_for__lt=today)

    daily_severity_status_list = []     # list for the DashboardSeverityStatusDaily model object
    daily_severity_status = None
    dashboard_name = ''
    device_name = ''
    for hourly_severity_status in last_day_timely_severity_status:
        if dashboard_name == hourly_severity_status.dashboard_name and device_name == hourly_severity_status.device_name:
            daily_severity_status = sum_severity_status(daily_severity_status, hourly_severity_status)
        else:
            daily_severity_status = DashboardSeverityStatusDaily(
                dashboard_name=hourly_severity_status.dashboard_name,
                device_name=hourly_severity_status.device_name,
                reference_name=hourly_severity_status.reference_name,
                processed_for=yesterday,
                warning=hourly_severity_status.warning,
                critical=hourly_severity_status.critical,
                ok=hourly_severity_status.ok,
                down=hourly_severity_status.down,
                unknown=hourly_severity_status.unknown
            )
            daily_severity_status_list.append(daily_severity_status)
            dashboard_name = hourly_severity_status.dashboard_name
            device_name = hourly_severity_status.device_name

    bulk_update_create.delay(daily_severity_status_list, action='create', model=DashboardSeverityStatusDaily)

    last_day_timely_severity_status.delete()


def calculate_daily_range_status(now):
    '''
    Calculate the status of dashboard from DashboardRangeStatusHourly model
    and create list of DashboardRangeStatusDaily model object for calculated data
    and then delete all data from the DashboardRangeStatusHourly model.

    :param now: datetime (example: timezone.now())

    return:
    '''
    # get the current timezone.
    tzinfo = timezone.get_current_timezone()
    # get today date according to current timezone and reset time to 12 o'clock.
    today = timezone.datetime(now.year, now.month, now.day, tzinfo=tzinfo)
    previous_day = now - timezone.timedelta(days=1)
    yesterday = timezone.datetime(previous_day.year, previous_day.month, previous_day.day, tzinfo=tzinfo)
    # get all result of yesterday only and order by 'dashboard_name' and'device_name'
    last_day_hourly_range_status = DashboardRangeStatusHourly.objects.order_by('dashboard_name',
            'device_name').filter(processed_for__gte=yesterday, processed_for__lt=today)

    daily_range_status_list = []
    daily_range_status = None
    dashboard_name = ''
    device_name = ''
    for hourly_range_status in last_day_hourly_range_status:
        if dashboard_name == hourly_range_status.dashboard_name and device_name == hourly_range_status.device_name:
            daily_range_status = sum_range_status(daily_range_status, hourly_range_status)
        else:
            daily_range_status = DashboardRangeStatusDaily(
                dashboard_name=hourly_range_status.dashboard_name,
                device_name=hourly_range_status.device_name,
                reference_name=hourly_range_status.reference_name,
                processed_for=yesterday,
                range1=hourly_range_status.range1,
                range2=hourly_range_status.range2,
                range3=hourly_range_status.range3,
                range4=hourly_range_status.range4,
                range5=hourly_range_status.range5,
                range6=hourly_range_status.range6,
                range7=hourly_range_status.range7,
                range8=hourly_range_status.range8,
                range9=hourly_range_status.range9,
                range10=hourly_range_status.range10,
                unknown=hourly_range_status.unknown
            )
            daily_range_status_list.append(daily_range_status)
            dashboard_name = hourly_range_status.dashboard_name
            device_name = hourly_range_status.device_name

    bulk_update_create.delay(daily_range_status_list, action='create', model=DashboardRangeStatusDaily)

    last_day_hourly_range_status.delete()

