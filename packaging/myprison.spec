Name:           myprison
Version:        0.4.0
Release:        1%{?dist}
Summary:        Terminal static blog manager for Hugo sites

License:        MIT
URL:            https://github.com/salvogendut/myprison
Source0:        %{name}-%{version}.tar.gz

BuildArch:      noarch
BuildRequires:  python3-devel
BuildRequires:  pyproject-rpm-macros

Requires:       python3 >= 3.9
Recommends:     hugo
Recommends:     git
Recommends:     rsync
Recommends:     gh
Recommends:     python3dist(textual) >= 0.85

%description
myprison is a terminal-native manager for Hugo-compatible static blogs. It
provides a default curses UI, an optional Textual UI, post management, Hugo
build and preview commands, deployment helpers, GitHub Pages support, and AI
assistance from the management menu.

%prep
%autosetup -n %{name}-%{version}

%generate_buildrequires
%pyproject_buildrequires

%build
%pyproject_wheel

%install
%pyproject_install
%pyproject_save_files myprison

%check
PYTHONPATH=%{buildroot}%{python3_sitelib} %{python3} - <<'PY'
import myprison
import myprison.app
import myprison.textual_main
PY

%files -f %{pyproject_files}
%doc README.md INSTALL.md USAGE.md
%{_bindir}/myprison
%{_bindir}/myprison-textual

%changelog
* Mon Aug 24 2026 Salvo Gendut <myprison@localhost> - 0.4.0-1
- Initial RPM package
