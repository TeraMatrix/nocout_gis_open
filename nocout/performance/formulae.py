"""
Store formulae for service.ServiceDataSource.
"""

def rta_null(rta=0):
    """

    :param rta:
    :return:
    """
    try:
        if float(rta) == 0:
            return rta
    except Exception as e:
        return None

    return rta


def display_time(seconds=0, granularity=4):
    """

    :param seconds: seconds on float
    :param granularity:
    :return:
    """

    try:
        seconds = float(seconds)
    except Exception:
        return 0

    intervals = (
        ('weeks', 604800),
        ('days', 86400),
        ('hours', 3600),
        ('minutes', 60),
        ('seconds', 1),
    )

    try:
        result = []
        for name, count in intervals:
            value = seconds // count
            if value:
                seconds -= value * count
                if value == 1:
                    name = name.rstrip('s')
                result.append("{} {}".format(value, name))
        return ', '.join(result[:granularity])

    except Exception as e:
        return None