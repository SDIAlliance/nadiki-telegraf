#load("logging.star", "log")
#load("json.star", "json")
def apply(metric):
  key = "-".join([metric.tags[x] for x in key_tags])
  last_metric = state.get(key)
  result = None
  if last_metric != None:
    result = deepcopy(metric)
    for f in metric.fields.keys():
        result.fields[f] = metric.fields[f] - last_metric.fields[f]
  state[key] = deepcopy(metric)
  return [result]
