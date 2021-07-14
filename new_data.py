import pandas,os,json
new_data = {}
for k,v in data.items():
    if k not in new_data.keys():
        new_data[k] = {}
    for hash, info in v.items():
        if hash == 'count':
            continue
        else:
            if hash not in new_data[k].keys():
                new_data[k][hash] = {}
                new_data[k][hash]['country'] = info['country']
                new_data[k][hash]['date'] = info['date']


with open(os.path.abspath('consolidated_bans.js'), 'w+') as f:
    json.dump(new_data, f, indent=4)
