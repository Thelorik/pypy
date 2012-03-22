
#ifndef STANDALONE_ENTRY_POINT
#  define STANDALONE_ENTRY_POINT   PYPY_STANDALONE
#endif

char *RPython_StartupCode(void);  /* forward */


/* prototypes */

int main(int argc, char *argv[]);


/* implementations */

#ifndef PYPY_NOT_MAIN_FILE

#ifndef PYPY_MAIN_FUNCTION
#define PYPY_MAIN_FUNCTION main
#endif

#ifdef MS_WINDOWS
#include "src/winstuff.c"
#endif

#ifdef __GNUC__
/* Hack to prevent this function from being inlined.  Helps asmgcc
   because the main() function has often a different prologue/epilogue. */
int pypy_main_function(int argc, char *argv[]) __attribute__((__noinline__));
#endif

int pypy_main_function(int argc, char *argv[])
{
    char *errmsg;
    int i, exitcode;
    RPyListOfString *list;

    pypy_asm_stack_bottom();
#ifdef PYPY_X86_CHECK_SSE2_DEFINED
    pypy_x86_check_sse2();
#endif
    instrument_setup();

#ifndef MS_WINDOWS
    /* this message does no longer apply to win64 :-) */
    if (sizeof(void*) != SIZEOF_LONG) {
        errmsg = "only support platforms where sizeof(void*) == sizeof(long),"
                 " for now";
        goto error;
    }
#endif

#ifdef MS_WINDOWS
    pypy_Windows_startup();
#endif

    errmsg = RPython_StartupCode();
    if (errmsg) goto error;

    exitcode = STANDALONE_ENTRY_POINT(argc, argv);

#ifdef RPY_ASSERT
    pypy_debug_alloc_results();
#endif

    if (RPyExceptionOccurred()) {
        /* print the RPython traceback */
        pypy_debug_catch_fatal_exception();
    }

    return exitcode;

 memory_out:
    errmsg = "out of memory";
 error:
    fprintf(stderr, "Fatal error during initialization: %s\n", errmsg);
    abort();
    return 1;
}

int PYPY_MAIN_FUNCTION(int argc, char *argv[])
{
    return pypy_main_function(argc, argv);
}

#endif /* PYPY_NOT_MAIN_FILE */
