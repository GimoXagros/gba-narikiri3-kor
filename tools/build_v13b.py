"""Build the cumulative, exact-16-MiB v1.3b candidate from immutable inputs."""
from build_v13a import main
from v13b_changes import build

if __name__ == '__main__':
    main('1.3b', build)
