load("logging.star", "log")
#load("json.star", "json")
def apply(metric):
  key = "-".join([metric.tags[x] for x in KEY_TAGS])
  last_metric = state.get(key)
  result = None
  if last_metric != None:
    result = deepcopy(metric)
    for f in metric.fields.keys():
        divisor = 1
        if CALCULATE_RATIO:
          divisor = (metric.time - last_metric.time) / 1000000000
          if divisor == 0:
            log.info("this tags = {}".format(metric.tags))
            log.info("last tags = {}".format(last_metric.tags))
        result.fields[f] = (metric.fields[f] - last_metric.fields[f]) / divisor
  state[key] = deepcopy(metric)
  return [result]
