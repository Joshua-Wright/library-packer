# library-packer

Bundles payload executable with shared libraries.
Executable and shared libraries are unpacked at runtime.
Uses `ldd` to find shared libraries, then embeds them into an executable using `objopy`.
Libraries are found at runtime by setting `LD_LIBRARY_PATH`.

## Example
```
$ echo 'main = putStrLn "Hello Haskell!"' > hello.hs
$ ghc hello.hs
[1 of 1] Compiling Main             ( hello.hs, hello.o )
Linking hello ...
$ ./hello
Hello Haskell!
$ ldd hello
        linux-vdso.so.1 =>  (0x00007ffc8415f000)
        libgmp.so.10 => /usr/lib/x86_64-linux-gnu/libgmp.so.10 (0x00007f939f7e0000)
        libm.so.6 => /lib/x86_64-linux-gnu/libm.so.6 (0x00007f939f4d7000)
        librt.so.1 => /lib/x86_64-linux-gnu/librt.so.1 (0x00007f939f2ce000)
        libdl.so.2 => /lib/x86_64-linux-gnu/libdl.so.2 (0x00007f939f0ca000)
        libc.so.6 => /lib/x86_64-linux-gnu/libc.so.6 (0x00007f939ed01000)
        /lib64/ld-linux-x86-64.so.2 (0x0000561cd841e000)
        libpthread.so.0 => /lib/x86_64-linux-gnu/libpthread.so.0 (0x00007f939eae3000)
$ ./packer.py hello hello.static
$ ./hello.static
Hello Haskell!
$ ldd hello.static
        not a dynamic executable
```

Note: distributing shared libraries in this way does not change the individual libraries licenses.
Make sure that those licenses allow for this.
