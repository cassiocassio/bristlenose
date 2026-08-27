# Copr's SRPM entry point.
#
# Copr's "make_srpm" build method runs this in a container that HAS network,
# which is the sanctioned way to get around mock having none. Everything the
# binary build needs is baked into the SRPM here.
#
#   copr-cli build-package --name bristlenose <project>
#
# Design: docs/design-fedora-packaging.md
srpm:
	dnf install -y python3-pip rpm-build curl
	rpm/make-srpm.sh "$(outdir)"
