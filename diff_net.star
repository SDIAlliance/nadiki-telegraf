load("logging.star", "log")
load("json.star", "json")
def apply(metric):
  last_metric = state.get(metric.tags["interface"])
  result = None
  if last_metric != None:
    result = deepcopy(metric)
    for f in metric.fields.keys():
        result.fields[f] = metric.fields[f] - last_metric.fields[f]
  state[metric.tags["interface"]] = deepcopy(metric)
  return [result]
