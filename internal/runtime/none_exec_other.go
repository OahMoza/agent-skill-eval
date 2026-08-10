//go:build !unix

package runtime

import (
	"os/exec"
	"time"
)

// Keep the platform-skipped process-group test buildable on non-Unix hosts.
const noneExecKillGrace = 1 * time.Second

// configureProcessGroup is a no-op on platforms without POSIX process groups.
func configureProcessGroup(_ *exec.Cmd, _ <-chan struct{}) {}
