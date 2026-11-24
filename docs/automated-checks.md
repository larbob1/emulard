# Automated synthetic checks

The workflow tests source patchers and builds the synthetic CPU and graphics capability probes. It does not retrieve the external runtime, access user data, upload diagnostics, execute a commercial title or verify real graphics hardware. Only the two synthetic executables are published as workflow artifacts.

The Windows graphics executable is compiled but not run in CI because the hosted environment is not a representative graphics device. The CPU fixture is run through CTest on Linux and Windows.

Inspect the workflow results before treating any check as passed. These checks are not a substitute for compiling and running the patched runtime on supported hardware.
