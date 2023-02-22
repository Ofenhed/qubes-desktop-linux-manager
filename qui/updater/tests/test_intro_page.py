# coding=utf-8
#
# The Qubes OS Project, http://www.qubes-os.org
#
# Copyright (C) 2023  Piotr Bartman <prbartman@invisiblethingslab.com>
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301,
# USA.
import pytest
from unittest.mock import patch

from qui.updater.intro_page import IntroPage, UpdateRowWrapper, UpdatesAvailable
from qui.updater.utils import ListWrapper, HeaderCheckbox


@patch('subprocess.check_output')
def test_populate_vm_list(
        mock_subprocess, real_builder, test_qapp,
        mock_next_button, mock_settings
):
    sut = IntroPage(real_builder, mock_next_button)
    test_qapp.expected_calls[
        ('test-standalone', "admin.vm.feature.Get", 'updates-available', None)
    ] = b"0\x00" + str(1).encode()
    # inconsistent output of qubes-vm-update, but it does not matter
    mock_subprocess.return_value = b'Following templates will be updated:'

    assert not sut.is_populated

    sut.populate_vm_list(test_qapp, mock_settings)

    assert sut.is_populated
    assert len(sut.list_store) == 4
    assert len(sut.get_vms_to_update()) == 1

    test_qapp.expected_calls[
        ('fedora-36', "admin.vm.feature.Get", 'updates-available', None)
    ] = b"0\x00" + str(1).encode()

    sut.populate_vm_list(test_qapp, mock_settings)
    assert len(sut.list_store) == 4
    assert len(sut.get_vms_to_update()) == 2


@pytest.mark.parametrize(
    "updates_available, expectations",
    (
        pytest.param((2, 6), (0, 2, 6, 12, 0)),
        pytest.param((6, 0), (0, 6, 12, 0)),
    ),
)
def test_on_header_toggled(
        real_builder, test_qapp, updates_available, expectations,
        mock_next_button, mock_settings, mock_list_store
):
    sut = IntroPage(real_builder, mock_next_button)

    # populate_vm_list
    sut.list_store = ListWrapper(UpdateRowWrapper, mock_list_store)
    for vm in test_qapp.domains:
        sut.list_store.append_vm(vm)

    assert len(sut.list_store) == 12

    for i, row in enumerate(sut.list_store):
        if i < updates_available[0]:
            value = True
        elif i < updates_available[1]:
            value = None
        else:
            value = False
        row.raw_row[row._UPDATES_AVAILABLE] = UpdatesAvailable.from_bool(value)
    sut.head_checkbox.state = HeaderCheckbox.NONE

    for expected in expectations:
        selected_num = len([row for row in sut.list_store if row.selected])
        assert selected_num == expected
        assert sut.checkbox_column_button.get_inconsistent() \
               and expected not in (0, 12) \
               or sut.checkbox_column_button.get_active() \
               and expected == 12 \
               or not sut.checkbox_column_button.get_active() \
               and expected == 0
        assert mock_next_button.sensitive or expected == 0
        sut.on_header_toggled(None)


def test_on_checkbox_toggled(
        real_builder, test_qapp,
        mock_next_button, mock_settings, mock_list_store
):
    sut = IntroPage(real_builder, mock_next_button)

    # populate_vm_list
    sut.list_store = ListWrapper(UpdateRowWrapper, mock_list_store)
    for vm in test_qapp.domains:
        sut.list_store.append_vm(vm)

    assert len(sut.list_store) == 12

    sut.head_checkbox.state = HeaderCheckbox.NONE
    sut.head_checkbox.set_buttons()

    # If button is inconsistent we do not care if it is active or not
    # (we do not use this value)

    # no selected row
    assert not sut.checkbox_column_button.get_inconsistent()
    assert not sut.checkbox_column_button.get_active()

    # only one row selected
    sut.on_checkbox_toggled(_emitter=None, path=(3,))

    assert sut.checkbox_column_button.get_inconsistent()

    for i in range(len(sut.list_store)):
        sut.on_checkbox_toggled(_emitter=None, path=(i,))

    # almost all rows selected (except one)
    assert sut.checkbox_column_button.get_inconsistent()

    sut.on_checkbox_toggled(_emitter=None, path=(3,))

    # all rows selected
    assert not sut.checkbox_column_button.get_inconsistent()
    assert sut.checkbox_column_button.get_active()

    sut.on_checkbox_toggled(_emitter=None, path=(3,))

    # almost all rows selected (except one)
    assert sut.checkbox_column_button.get_inconsistent()

    for i in range(len(sut.list_store)):
        if i == 3:
            continue
        sut.on_checkbox_toggled(_emitter=None, path=(i,))

    # no selected row
    assert not sut.checkbox_column_button.get_inconsistent()
    assert not sut.checkbox_column_button.get_active()
