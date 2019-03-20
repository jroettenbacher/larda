#!/usr/bin/python


import datetime, sys
import numpy as np
from numba import jit
import pprint as pp

def ident(x):
    return x


def get_converter_array(string, **kwargs):
    """colletion of converters that works on arrays
    combines time, range and varconverters (i see no conceptual separation here)
   
    the maskconverter becomes relevant, if the order is no
    time, range, whatever (as in mira spec)

    Returns:
        (varconverter, maskconverter) which both are functions
    """
    if string == 'since20010101':
        return lambda x: x + dt_to_ts(datetime.datetime(2001, 1, 1)), ident
    elif string == 'unix':
        return lambda x: x, ident
    elif string == 'since19691231':
        return lambda x: x + dt_to_ts(datetime.datetime(1969, 12, 31, 23)), ident
    elif string == 'beginofday':
        if 'ncD' in kwargs.keys():
            return (lambda h: (h.astype(np.float64) * 3600. + \
                               float(dt_to_ts(datetime.datetime(kwargs['ncD'].year,
                                                                kwargs['ncD'].month,
                                                                kwargs['ncD'].day)))),
                    ident)

    elif string == "km2m":
        return lambda x: x * 1000., ident
    elif string == "sealevel2range":
        return lambda x: x - kwargs['altitude'], ident

    elif string == 'z2lin':
        return z2lin, ident
    elif string == 'lin2z':
        return lin2z, ident
    elif string == 'switchsign':
        return lambda x: -x, ident

    elif string == "mira_azi_offset":
        return lambda x: (x + kwargs['mira_azi_zero']) % 360, ident

    elif string == 'transposedim':
        return np.transpose, np.transpose
    elif string == 'transposedim+invert3rd':
        return transpose_and_invert, transpose_and_invert
    elif string == 'divideby2':
        return divide_by(2.), ident
    elif string == "none":
        return ident, ident
    else:
        raise ValueError("rangeconverter {} not defined".format(string))


def transpose_and_invert(var):
    return np.transpose(var)[:, :, ::-1]


def divide_by(val):
    return lambda var: var / val


def flatten(xs):
    """flatten inhomogeneous deep lists
    e.g. ``[[1,2,3],4,5,[6,[7,8],9],10]``
    """
    result = []
    if isinstance(xs, (list, tuple)):
        for x in xs:
            result.extend(flatten(x))
    else:
        result.append(xs)
    return result


def since2001_to_dt(s):
    """seconds since 2001-01-01 to datetime"""
    # return (dt - datetime.datetime(1970, 1, 1)).total_seconds()
    return datetime.datetime(2001, 1, 1) + datetime.timedelta(seconds=s)


def dt_to_ts(dt):
    """datetime to unix timestamp"""
    # return dt.replace(tzinfo=datetime.timezone.utc).timestamp()
    return (dt - datetime.datetime(1970, 1, 1)).total_seconds()


def ts_to_dt(ts):
    """unix timestamp to dt"""
    return datetime.datetime.utcfromtimestamp(ts)


def argnearest(array, value):
    """find the index of the nearest value in a sorted array
    for example time or range axis

    Args:
        array (np.array): sorted array with values
        value: value to find
    Returns:
        index  
    """
    i = np.searchsorted(array, value) - 1
    if not i == array.shape[0] - 1 \
            and np.abs(array[i] - value) > np.abs(array[i + 1] - value):
        i = i + 1
    return i


def nearest(array, pivot):
    """find the nearest value to a given one

    Args:
        array (np.array): sorted array with values
        pivot: value to find
    Returns:
        value with smallest distance
    """
    return min(array, key=lambda x: abs(x - pivot))


def lin2z(array):
    """linear values to dB (for np.array or single number)"""
    return 10 * np.ma.log10(array)


def z2lin(array):
    """dB to linear values (for np.array or single number)"""
    return 10 ** (array / 10.)


def fill_with(array, mask, fill):
    """fill an array where mask is true with fill value"""
    filled = array.copy()
    filled[mask] = fill
    return filled


def _method_info_from_argv(argv=None):
    """Command-line -> method call arg processing.

    - positional args:
            a b -> method('a', 'b')
    - intifying args:
            a 123 -> method('a', 123)
    - json loading args:
            a '["pi", 3.14, null]' -> method('a', ['pi', 3.14, None])
    - keyword args:
            a foo=bar -> method('a', foo='bar')
    - using more of the above
            1234 'extras=["r2"]'  -> method(1234, extras=["r2"])

    @param argv {list} Command line arg list. Defaults to `sys.argv`.
    @returns (<method-name>, <args>, <kwargs>)

    Reference: http://code.activestate.com/recipes/577122-transform-command-line-arguments-to-args-and-kwarg/
    """
    import json
    import sys
    if argv is None:
        argv = sys.argv

    method_name, arg_strs = argv[0], argv[1:]
    args = []
    kwargs = {}
    for s in arg_strs:
        if s.count('=') == 1:
            key, value = s.split('=', 1)
        else:
            key, value = None, s
        try:
            value = json.loads(value)
        except ValueError:
            pass
        if key:
            kwargs[key] = value
        else:
            args.append(value)
    return method_name, args, kwargs



def reshape_spectra(data):
    """This function reshapes time, range and var variables of a data container and returns numpy arrays.

    Args:
        data (dict): data container

    Returns:
        list with

        - ts (numpy.array): time stamp numpy array, dim = (n_time,)
        - rg (numpy.array): range stamp numpy array, dim = (n_range,)
        - var (numpy.array): values of the spectra numpy array, dim = (n_time, n_range, n_vel)
    """
    n_ts, n_rg, n_vel = data['ts'].size, data['rg'].size, data['vel'].size

    if data['dimlabel'] == ['time', 'range', 'vel']:
        ts = data['ts'].copy()
        rg = data['rg'].copy()
        var = data['var'].copy()
    elif data['dimlabel'] == ['time', 'vel']:
        ts = data['ts'].copy()
        rg = np.reshape(data['rg'], (n_rg,))
        var = np.reshape(data['var'], (n_ts, 1, n_vel))
    elif data['dimlabel'] == ['range', 'vel']:
        ts = np.reshape(data['ts'].copy(), (n_ts,))
        rg = data['rg'].copy()
        var = np.reshape(data['var'], (1, n_rg, n_vel))
    elif data['dimlabel'] == ['vel']:
        ts = np.reshape(data['ts'].copy(), (n_ts,))
        rg = np.reshape(data['rg'], (n_rg,))
        var = np.reshape(data['var'], (1, 1, n_vel))
    else:
        raise TypeError('Wrong data format in plot_spectra')

    return ts, rg, var


def pformat(data, verbose=False):
    """return a pretty string from a data_container"""
    string = []
    string.append("== data container: system {} name {}  ==".format(data["system"], data["name"]))
    string.append("dimlabel    {}".format(data["dimlabel"]))
    if "time" in data["dimlabel"]:
        string.append("timestamps  {} {} to {}".format(
            data["ts"].shape,
            ts_to_dt(data["ts"][0]), ts_to_dt(data["ts"][-1])))
    elif "ts" in data.keys():
        string.append("timestamp   {}".format(ts_to_dt(data['ts'])))
    if "range" in data["dimlabel"]:
        string.append("range       {} {:7.2f} to {:7.2f}".format(
            data["rg"].shape,
            data["rg"][0], data["rg"][-1]))
        string.append("rg_unit     {}".format(data["rg_unit"]))
    elif "rg" in data.keys():
        string.append("range       {}".format(data['rg']))
        string.append("rg_unit     {}".format(data["rg_unit"]))
    if "vel" in data.keys():
        string.append("vel         {}  {:5.2f} to {:5.2f}".format(
            data["vel"].shape,
            data["vel"][0], data["vel"][-1]))
    if not np.all(data["mask"]):
        string.append("var         {}  min {:7.2e} max {:7.2e}".format(
            data['var'].shape,
            np.min(data['var'][~data['mask']]), np.max(data['var'][~data['mask']])))
        string.append("            mean {:7.2e} median {:7.2e}".format(
            np.mean(data['var'][~data['mask']]), np.median(data['var'][~data['mask']])))
    string.append("mask        {:4.1f}%".format(
        np.sum(data["mask"])/data['mask'].ravel().shape[0]*100.))
    string.append("var_unit    {}".format(data["var_unit"]))
    string.append("var_lims    {}".format(data["var_lims"]))
    string.append("default colormap {}".format(data["colormap"]))
    if verbose:
        string.append("filenames")
        string.append(pp.pformat(data["filename"], indent=2))
        string.append("paraminfo".format())
        string.append(pp.pformat(data['paraminfo'], indent=2))
    return "\n".join(string)


def pprint(data, verbose=False):
    """print a pretty representation of the data container"""
    print(pformat(data, verbose=verbose))


def extract_case_from_excel_sheet(data_loc, sheet_nr=0):
    """This function extracts information from an excel sheet. It can be used for different scenarios.
    The first row of the excel sheet contains the headline, defined as follows:

    +----+-------+-------+-------+-------+-------+-------+-------+-------+
    |    |   A   |   B   |   C   |   D   |   E   |   F   |   G   |   H   |
    +----+-------+-------+-------+-------+-------+-------+-------+-------+
    |  1 |  date | start |  end  |   h0  |  hend |  MDF  |   nf  | notes |
    +----+-------+-------+-------+-------+-------+-------+-------+-------+


    The following rows contain the cases of interest. Make sure that the ALL the data in the excel sheet is formatted as
    string! The data has to be provided in the following syntax:

        - date (string): format YYYYMMDD
        - start (string): format HHMMSS
        - end (string): format HHMMSS
        - h0 (string): minimum height
        - hend (string): maximum height
        - MDF (string): name of the MDF used for this case
        - nf (string): noise factor
        - notes (string): additional notes for the case (stored but not in use by the program)

    Args:
        data_loc (string): path to the excel file (make sure the data_loc contains the suffix .xlsx)
        sheet_nr (integer): number of the desired excel sheet

    Returns:
        case_list contains the information for all cases
            
        - begin_dt (datetime object): start of the time interval
        - end_dt (datetime object): end of the time interval
        - plot_range (list): height interval
        - MDF_name (string): name of MDF used for this case
        - noisefac (string): number of standard deviations above mean noise level
        - notes (string): additional notes for the user
            
    """

    import xlrd

    excel_sheet = xlrd.open_workbook(data_loc)
    sheet = excel_sheet.sheet_by_index(sheet_nr)
    case_list = []

    # exclude header from data
    for icase in range(1, sheet.nrows):
        irow = sheet.row_values(icase)
        irow[:3] = [int(irow[i]) for i in range(3)]

        if irow[7] != 'ex':
            case_list.append({
                'begin_dt': datetime.datetime.strptime(str(irow[0]) + ' ' + str(irow[1]), '%Y%m%d %H%M%S'),
                'end_dt': datetime.datetime.strptime(str(irow[0]) + ' ' + str(irow[2]), '%Y%m%d %H%M%S'),
                'plot_range': [float(irow[3]), float(irow[4])],
                'MDF_name': irow[5],
                'noisefac': irow[6],
                'notes': irow[7]})

    return case_list
