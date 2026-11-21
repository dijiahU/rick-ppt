"""Language is an immutable task choice, not a guess from the UI or brief."""
LANGUAGES={'en':'English','fr':'French','es':'Spanish','zh-CN':'Simplified Chinese','ja':'Japanese'}

def presentation_request(task):
    value={key:task[key] for key in ('title','brief','pages','style')}
    mode=task.get('mode','create')
    if mode not in ('create','edit'):
        raise ValueError('Unsupported task mode')
    value['mode']=mode
    if mode=='edit':
        value['pages']=None
    language=task.get('language')
    if language is not None and (not isinstance(language,str) or language not in LANGUAGES):
        raise ValueError('Unsupported presentation language')
    value['language']=language
    backend=task.get('execution_backend')
    if backend not in (None,'api','codex'):
        raise ValueError('Unsupported task execution backend')
    if backend is not None:value['execution_backend']=backend
    return value

def language_instruction(task):
    language=presentation_request(task)['language']
    if language is None:
        return 'This legacy task has no saved language choice. Follow an explicit requested output language, otherwise use the main language of its topic/brief; do not impose English retroactively.'
    return (f'The submitted primary presentation language is {LANGUAGES[language]} ({language}): use it for titles, body, '
            'labels, captions, notes and the completion summary, even if the brief is in another language. '
            'Honor explicitly requested supplementary languages as secondary copy; this choice does not cancel an explicit '
            'supplementary-language requirement. Otherwise add no bilingual or decorative English labels. Keep proper names, '
            'code and source titles as needed, and check rendered pages for missing glyphs and overflow.')
