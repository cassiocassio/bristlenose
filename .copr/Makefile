# Copr's SRPM entry point.
#
# Copr's "make_srpm" build method runs this in a container that HAS network,
# which is the sanctioned way around mock having none. Everything the binary
# build needs is baked into the SRPM here.
#
#   copr-cli buildscm <project> \
#       --clone-url https://github.com/cassiocassio/bristlenose.git \
#       --method make_srpm --spec rpm/bristlenose.spec
#
# python3.14 is installed and named explicitly rather than using whatever
# python3 this container happens to ship. The wheelhouse is built for ONE
# python minor; if it does not match the TARGET chroot, `pip install
# --no-index` fails on every heavy dependency at once, inside mock. Fedora 43
# is python 3.14, and Copr no longer offers a fedora-42 chroot — so enabling a
# chroot with a different python means changing this line too.
#
# Design: docs/design-fedora-packaging.md
srpm:
	dnf install -y python3.14 python3-pip rpm-build curl
	BN_PYTHON=python3.14 rpm/make-srpm.sh "$(outdir)"
