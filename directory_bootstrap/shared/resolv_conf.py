# Copyright (C) 2015 Sebastian Pipping <sebastian@pipping.org>
# Licensed under AGPL v3 or later




def filter_copy_resolv_conf(messenger, abs_etc_resolv_conf, output_filename):
    messenger.info('Writing file "%s" (based on file "%s")...'
            % (output_filename, abs_etc_resolv_conf))

    with open(abs_etc_resolv_conf) as input_f:
        with open(output_filename, 'w') as output_f:
            for l in input_f:
                line = l.rstrip()
                if line.startswith('nameserver'):
                    print(line, file=output_f)
