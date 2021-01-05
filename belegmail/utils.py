import collections
import datetime
import enum
import re


class PROCESSING_RESULT(enum.Enum):
    ERROR = 0
    UPLOADED = 1
    IGNORE = 2
    PROCESSED = 3
    OTHER = 4


def normalize_date_TTMMJJJJ(data):
    data = "".join(data.split())
    if not data:
        return ""

    date = datetime.datetime.strptime(data, "%d.%m.%Y")
    return date.strftime("%Y-%m-%d")


def symmetric_difference(
    list_a,
    list_b,
    map_to_equiv=lambda x: x,
    transform_a=lambda a: a,
    transform_b=lambda b: b,
):
    def helper_transform(item, transform):
        t_item = transform(item)
        return (map_to_equiv(t_item), t_item, item)

    tmp_a = list(helper_transform(a, transform_a) for a in list_a)
    tmp_b = list(helper_transform(b, transform_b) for b in list_b)

    ctr_a = collections.Counter(m_a for (m_a, t_a, a) in tmp_a)
    ctr_b = collections.Counter(m_b for (m_b, t_b, b) in tmp_b)

    only_in_a = []
    only_in_b = []

    for m_a, t_a, a in tmp_a:
        if ctr_b[m_a]:
            ctr_b[m_a] -= 1
        else:
            only_in_a.append(a)

    for m_b, t_b, b in tmp_b:
        if ctr_a[m_b]:
            ctr_a[m_b] -= 1
        else:
            only_in_b.append(b)

    return only_in_a, only_in_b


class LoginError(Exception):
    pass


class TemporaryError(Exception):
    pass
