#!/bin/bash

# we assume this script is <ardour-src>/tools/x-win/compile.sh
pushd "`/usr/bin/dirname \"$0\"`" > /dev/null; this_script_dir="`pwd`"; popd > /dev/null
cd "$this_script_dir/../.."
test -f gtk2_ardour/wscript || exit 1

# Ensure the environment variable is set globally
export _MSYS_ENV=true
export XARCH=x86_64 # or x86_64
export _ROOT="${HOME}"
export MAKEFLAGS=-j4

if [[ "$XARCH" = "x86_64" || "$XARCH" = "amd64" ]]; then
	echo "Target: 64bit Windows (x86_64)"
	export XPREFIX=x86_64-w64-mingw32
	export WARCH=w64
else
	echo "Target: 32 Windows (i686)"
	export XPREFIX=i686-w64-mingw32
	export WARCH=w32
fi

export PREFIX="/mingw64"

if test -z "${ARDOURCFG}"; then
	if test -f ${PREFIX}/include/pa_asio.h; then
		ARDOURCFG="--with-backends=jack,dummy,portaudio"
	else
		ARDOURCFG="--with-backends=jack,dummy"
	fi
fi

#if [ "$(id -u)" = "0" ]; then
	#fixup mingw64 ccache for now
	if test -d /usr/lib/ccache -a -f /usr/bin/ccache; then
		export PATH="/usr/lib/ccache:${PATH}"
		cd /usr/lib/ccache
		test -L ${XPREFIX}-gcc || ln -s ../../bin/ccache ${XPREFIX}-gcc
		test -L ${XPREFIX}-g++ || ln -s ../../bin/ccache ${XPREFIX}-g++
		cd - > /dev/null
	fi
#fi

################################################################################
set -e
export PKG_CONFIG_PATH=${PKG_CONFIG_PATH}:${PREFIX}/lib/pkgconfig

export CC=$(which ${XPREFIX}-gcc.exe)
export CXX=$(which ${XPREFIX}-g++.exe)
export CPP=$(which ${XPREFIX}-cpp.exe)
export AR=$(which ${XPREFIX}-ar.exe)
export LD=$(which ${XPREFIX}-ld.exe)
export NM=$(which ${XPREFIX}-nm.exe)
export AS=$(which ${XPREFIX}-as.exe)
export STRIP=$(which ${XPREFIX}-strip.exe)
export WINRC=$(which ${XPREFIX}-windres.exe)
export RANLIB=$(which ${XPREFIX}-ranlib.exe)
export DLLTOOL=$(which ${XPREFIX}-dlltool.exe)

if grep -q optimize <<<"$ARDOURCFG"; then
	OPT=""
else
	# debug-build luabindings.cc, has > 60k symbols.
	# -Wa,-mbig-obj has an unreasonable long build-time
	# so libs/ardour/wscript only uses it for luabindings.cc.
	# session.cc is also big, -Og to the rescue.
	OPT=" -Og"
fi

CFLAGS="-mstackrealign$OPT" \
CXXFLAGS="-mstackrealign$OPT" \
LDFLAGS="-L${PREFIX}/lib" \
DEPSTACK_ROOT="$PREFIX" \
./waf configure \
	--keepflags \
	--dist-target=mingw \
	--also-include=${PREFIX}/include \
	$ARDOURCFG \
	--prefix=${PREFIX} \
	--libdir=${PREFIX}/lib

./waf ${CONCURRENCY}

#if [ "$(id -u)" = "0" ]; then
#	if [ -n "$_MSYS_ENV" ]; then
#		# MSYS2
#		pacman -S --noconfirm gettext
#	else
#		# Debian/Ubuntu
#		apt-get -qq -y install gettext
#	fi
#fi
#echo " === build complete, creating translations"
./waf i18n
#echo " === done"
