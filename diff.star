##
## This Starlark script remembers the latest metric for a specific key
## and calculates the different between the next occurcence and the
## last one. This converts counter metrics into gauges.
## Optionally, it can divide the result by the number of elapsed seconds.
## This is probably only useful for turning CPU seconds into a
## fraction of time that the CPU was busy.
##
## These constants can be set in the telegraf.conf:
## - KEY_TAGS, an array of tag names whose values will be concatenated
##   to get a unique key, e.g. "device" for IO metrics
## - CALCULATE_RATIO: if set to "true", the resulting difference
##   will also be devided by the elapsed seconds since the last data
##   point for the same key.
##

load("logging.star", "log")
#load("json.star", "json")
def apply(metric):
  key = "-".join([metric.measurement] + [metric.tags[x] for x in KEY_TAGS])
  last_metric = state.get(key)
  result = None
  if last_metric != None:
    result = deepcopy(metric)
    for f in metric.fields.keys():
        divisor = 1
        if CALCULATE_RATIO:
          divisor = (metric.time - last_metric.time) / 1000000000
          if divisor == 0:
            log.info("Divisor is 0 between these two metrics (maybe your key is not unique?):")
            log.info("this tags = {}".format(metric.tags))
            log.info("last tags = {}".format(last_metric.tags))
        result.fields[f] = (metric.fields[f] - last_metric.fields[f]) / divisor
  state[key] = deepcopy(metric)
  return [result]
