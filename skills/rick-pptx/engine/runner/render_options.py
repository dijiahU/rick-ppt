"""Restricted PDF export options accepted by the task render broker."""
import json
import re


def pdf_filter(page=None):
    if page is not None and (type(page) is not int or not 1<=page<=200):
        raise ValueError('Invalid PDF page')
    options={'ExportHiddenSlides':{'type':'boolean','value':'true'}}
    if page is not None:options['PageRange']={'type':'string','value':str(page)}
    return 'pdf:impress_pdf_Export:'+json.dumps(options,separators=(',',':'))


def requested_page(args):
    value=args[args.index('--convert-to')+1]
    if value in ('pdf','pdf:impress_pdf_Export'):return None
    prefix='pdf:impress_pdf_Export:'
    if not value.startswith(prefix):raise ValueError('Only Impress PDF export is permitted')
    options=json.loads(value[len(prefix):])
    if not isinstance(options,dict) or set(options)-{'ExportHiddenSlides','PageRange'}:
        raise ValueError('Unsupported PDF export option')
    hidden=options.get('ExportHiddenSlides')
    if 'ExportHiddenSlides' in options and hidden!={'type':'boolean','value':'true'}:
        raise ValueError('Hidden slides must remain available')
    entry=options.get('PageRange')
    if 'PageRange' not in options:return None
    if (not isinstance(entry,dict) or set(entry)!={'type','value'} or entry['type']!='string'
            or not isinstance(entry['value'],str) or not re.fullmatch(r'[1-9][0-9]{0,2}',entry['value'])):
        raise ValueError('One positive PDF page is required')
    page=int(entry['value'])
    if page>200:raise ValueError('PDF page exceeds the supported limit')
    return page
