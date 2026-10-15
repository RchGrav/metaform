  if os.environ.get('METAFORM_ROLE') not in (None, '', 'none'):
+        settings.refuse_held_control((key for key in parsed.switches if key in verb.switches), folder)
    if verb.caution and not parsed.confirm: