#!/usr/bin/env python3 
import sys
import os
import shutil
import subprocess

tmpfolder     = ".tmp-package/"
main_filename = "main.c"

def sanatize_name(name):
    for x in "!@#$%^&*(){}[]:;\"'<>,./?\\|-+=":
        name = name.replace(x, '_')
    return name

def copy_pack_file(path, out_filename):
    objcopy = subprocess.run(['objcopy', '-I', 'binary', '-B', 'i386:x86-64', '-O', 'elf64-x86-64', path, out_filename])

def lib_data_start(lib_name):  return "(&_binary_"           + sanatize_name(lib_name) + "_start[0])"
def lib_data_length(lib_name): return "((long int)&_binary_" + sanatize_name(lib_name) + "_size)"
def write_decl(outfile, libs, payload):
    # objcopy puts the size as the address of the symbol
    for lib in libs:
        outfile.write('extern const char _binary_'     + sanatize_name(lib) + '_start[];\n')
        outfile.write('extern const long int _binary_' + sanatize_name(lib) + '_size;\n')

    outfile.write('extern const char _binary_'     + sanatize_name(payload) + '_start[];\n')
    outfile.write('extern const long int _binary_' + sanatize_name(payload) + '_size;\n')

if __name__ == "__main__":

    if len(sys.argv) < 3:
        print("usage:", sys.argv[0], "<input> <output>")
        exit(1)

    # find libraries
    payload = sys.argv[1]
    target  = sys.argv[2]
    ldd_output = subprocess.run(["ldd", payload], stdout=subprocess.PIPE)
    libs = []
    for line in ldd_output.stdout.decode('utf-8').split('\n'):
        if " => " in line:
            lib = line.split(' ')[2]
            if lib != '': 
                libs.append(lib)

    # make libs folder
    if not os.path.exists(tmpfolder):
        os.mkdir(tmpfolder)
    # make master libs C file
    with open(tmpfolder+main_filename, "w") as out:
        # write starting info
        out.write("""
        #include <stdlib.h>
        #include <stdint.h>
        #include <unistd.h>
        #include <fcntl.h>
        #include <sys/stat.h>
        #include <wait.h>
        #include <stdio.h>
        #include <string.h>
        #include <errno.h>
        """)
        # expose extern variables
        write_decl(out, libs, payload)

        out.write("""
        int main(int argc, char **argv) {
            int fd;
            char ld_lib_path[512] = {0};
            char libpathbuf[256]  = {0};
            char baselibpath[256] = {0};
            char *tmppath         = "/tmp/";
            if (getenv("TMPDIR")) {
                tmppath = getenv("TMPDIR");
            }
            sprintf(baselibpath, "%s/lib_XXXXXX", tmppath);
        """)
        for lib in libs:
            out.write("""
                strcpy(libpathbuf, baselibpath);
                fd = mkstemp(libpathbuf);
                unlink(libpathbuf);
                write(fd, {start}, {length});
                sprintf(libpathbuf, "/dev/fd/%i", fd);
                strcat(ld_lib_path, ":");
                strcat(ld_lib_path, libpathbuf);
            """.format(
                basename=os.path.basename(lib), 
                start=lib_data_start(lib), 
                length=lib_data_length(lib))
            )
        # write payload (close and re-open to get read-only)
        out.write("""
            sprintf(libpathbuf, "%s/%i", tmppath, getpid());
            fd = open(libpathbuf, O_RDWR | O_CREAT | O_EXCL, 0700);
            write(fd, {start}, {length});
            close(fd);
            fd = open(libpathbuf, O_RDONLY);
            unlink(libpathbuf);
            sprintf(libpathbuf, "/dev/fd/%i", fd);
        """.format(
            start=lib_data_start(payload), 
            length=lib_data_length(payload))
        )

        out.write("""
            char envbuf[1024];
            sprintf(envbuf, "LD_PRELOAD=%s", ld_lib_path+1);
            char *env[] = {envbuf, NULL};
            fexecve(fd, argv, env);
        }
        """)

        # payload
        copy_pack_file(payload, tmpfolder+'payload')
        # lib data
        for lib in libs:
            basename       = os.path.basename(lib)
            sanatized_name = sanatize_name(basename)
            copy_pack_file(lib, tmpfolder+sanatized_name)

    gcc = ['cc', '-Wno-unused-result','-static', '-Os', '-o', target, tmpfolder+main_filename, tmpfolder+'payload'] + [tmpfolder+sanatize_name(os.path.basename(l)) for l in libs]
    subprocess.run(gcc)
    shutil.rmtree(tmpfolder)

