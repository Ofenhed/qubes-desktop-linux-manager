# -*- encoding: utf8 -*-
#
# The Qubes OS Project, http://www.qubes-os.org
#
# Copyright (C) 2022 Marta Marczykowska-Górecka
#                               <marmarta@invisiblethingslab.com>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation; either version 2.1 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License along
# with this program; if not, see <http://www.gnu.org/licenses/>.
"""
Class for handling a list of exceptions, such as for updateProxy.
"""
from copy import deepcopy
from typing import Optional, List, Callable

import qubesadmin
import qubesadmin.vm
from qrexec.policy.parser import Rule
from .page_handler import PageHandler

from .policy_handler import PolicyHandler
from .policy_rules import SimpleVerbDescription, RuleDispVM
from .rule_list_widgets import RuleListBoxRow, ErrorRuleRow, \
    DispvmRuleRow

import gi

from ..widgets.gtk_widgets import QubeName

gi.require_version('Gtk', '3.0')
from gi.repository import Gtk

class PolicyExceptionsHandler:
    """
    Class for handling a list of policy exceptions
    """
    def __init__(self, gtk_builder: Gtk.Builder, prefix: str,
                 row_func: Callable[[Rule, bool], Gtk.ListBoxRow],
                 new_rule: Callable[..., Rule],
                 exclude_rule: Optional[Callable[[Rule], bool]] = None):
        """
        :param gtk_builder: Gtk.Builder instance
        :param prefix: prefix for widgets; expects a prefix_exception_list
        ListBox and prefix_add_rule_button Button
        :param row_func: function that returns expected ListBoxRows
        :param new_rule: function that returns a new Rule
        :param exclude_rule: optional function that excludes some rules from
        being shown; if True, exclude rule
        """
        self.exclude_rule = exclude_rule
        self.row_func = row_func  # takes a Rule and new/true/false
        self.new_rule = new_rule

        self.initial_rules: List[Rule] = []
        self.rule_list: Gtk.ListBox = gtk_builder.get_object(
            f'{prefix}_exception_list')

        self.add_button: Gtk.Button = gtk_builder.get_object(
            f'{prefix}_add_rule_button')

        self.error_box: Gtk.Box = gtk_builder.get_object(f'{prefix}_error_box')
        self.error_list: Gtk.ListBox = gtk_builder.get_object(
            f'{prefix}_error_list')

        # connect events
        self.rule_list.connect('row-activated', self._rule_clicked)
        self.add_button.connect("clicked", self.add_new_rule)

        self._errors: List[Rule] = []

    def load_rules(self, rules: List[Rule]):
        """Load provided rules."""
        self.initial_rules.clear()
        for rule in rules:
            if self.exclude_rule and self.exclude_rule(rule):
                continue
            self.initial_rules.append(rule)

        for child in self.rule_list.get_children():
            self.rule_list.remove(child)

        self.clear_errors()

        for rule in self.initial_rules:
            try:
                self.rule_list.add(self.row_func(rule, False))
            except Exception:  # pylint: disable=broad-except
                self.add_error(rule)

    def add_new_rule(self, *_args):
        """Add a new rule."""
        self.close_all_edits()
        new_row = self.row_func(self.new_rule(), True)
        self.rule_list.add(new_row)
        new_row.activate()

    def _rule_clicked(self, _list_box, row: RuleListBoxRow, *_args):
        if row.editing:
            # if the current row was clicked, nothing should happen
            return
        self.close_all_edits()
        row.set_edit_mode(True)

    def get_unsaved(self) -> str:
        self.close_all_edits()

        if len(self.initial_rules) != len(self.current_rules):
            return "Policy rules"
        for rule1, rule2 in zip(self.initial_rules, self.current_rules):
            if str(rule1) != str(rule2):
                return "Policy rules"
        return ""


    @property
    def current_rows(self) -> List[RuleListBoxRow]:
        """Get currently existing rows."""
        return self.rule_list.get_children()

    @property
    def current_rules(self) -> List[Rule]:
        rules = [row.rule.raw_rule for row in self.current_rows if
         not row.is_new_row or row.changed_from_initial]
        return rules

    def close_all_edits(self):
        """Close all edited rows."""
        PolicyHandler.close_rows_in_list(self.rule_list.get_children())

    def add_error(self, rule: Rule):
        self._errors.append(rule)
        self.error_box.set_visible(True)
        self.error_box.show_all()
        self.error_list.add(ErrorRuleRow(rule))
        self.error_list.show_all()

    def clear_errors(self):
        self._errors.clear()
        self.error_box.set_visible(False)
        for child in self.error_list.get_children():
            self.error_list.remove(child)

    @staticmethod
    def verify_rule_against_rows(other_rows: List[RuleListBoxRow],
                                 row: RuleListBoxRow,
                                 new_source: str, new_target: str,
                                 new_action: str) -> Optional[str]:
        """
        Verify correctness of a rule with new_source, new_target and new_action
        if it was to be associated with provided row. Return None if rule would
        be correct, and string description of error otherwise.
        """
        for other_row in other_rows:
            if other_row == row:
                continue
            if other_row.rule.is_rule_conflicting(new_source, new_target,
                                                  new_action):
                return str(other_row)
        return None

    def verify_new_rule(self, row: RuleListBoxRow,
                        new_source: str, new_target: str,
                        new_action: str) -> Optional[str]:
        """
        Verify correctness of a rule with new_source, new_target and new_action
        if it was to be associated with provided row. Return None if rule would
        be correct, and string description of error otherwise.
        """
        return self.verify_rule_against_rows(self.current_rows, row,
                                      new_source, new_target, new_action)


class DispvmExceptionHandler(PageHandler):
    def __init__(self, gtk_builder: Gtk.Builder,
                 qapp: qubesadmin.Qubes,
                 service_name: str,
                 prefix: str,
                 policy_manager,
                 policy_file_name: str
                 ):
        """
        Handler for various dispvm-related exception lists
        :param gtk_builder: Gtk.Builder instance
        :param qapp: Qubes object
        :param service_name: name of the service to be used
        :param prefix: prefix for widgets; expects a
            prefix_exception_list Gtk.ListBox,
            prefix_add_rule_button Gtk.Button,
            prefix_current_state_box Gtk.Box,
            prefix_error_box Gtk.Box,
            prefix_problem_box Gtk.Box,
            prefix_error_list Gtk.ListBox,
            prefix_problem_files_list Gtk.ListBox
        :param policy_manager: PolicyManager object
        :param policy_file_name: name of the policy file
        """
        self.qapp = qapp
        self.service_name = service_name
        self.policy_manager = policy_manager
        self.policy_file_name = policy_file_name

        self.list_handler = PolicyExceptionsHandler(
            gtk_builder=gtk_builder,
            prefix=prefix,
            row_func=self._get_row,
            new_rule=self._new_rule)

        self.current_state_box: Gtk.Box = gtk_builder.get_object(
            f'{prefix}_current_state_box')
        self.current_state_widget: Optional[Gtk.Box] = None

        self.initial_rules, self.current_token = \
            self.policy_manager.get_rules_from_filename(
                self.policy_file_name, "")

        self.initialize()

    def initialize(self):
        if self.current_state_widget:
            self.current_state_box.remove(self.current_state_widget)

        def_dvm = self.qapp.domains[self.qapp.local_name].default_dispvm
        self.current_state_widget = QubeName(def_dvm)
        self.current_state_box.add(self.current_state_widget)

        self.list_handler.load_rules(self.initial_rules)

    def _get_row(self, rule: Rule, new: bool = False):
        return DispvmRuleRow(
            parent_handler=self.list_handler,
            rule=RuleDispVM(rule),
            qapp=self.qapp,
            verb_description=SimpleVerbDescription({
                "ask": "and default to",
                "allow": "use",
                "deny": "open in disposable qube"
            }),
            is_new_row=new,
        )

    def _new_rule(self) -> Rule:
        return self.policy_manager.new_rule(
            service=self.service_name, source='@anyvm',
            target='@dispvm',
            action='allow target=@dispvm')

    def get_unsaved(self) -> str:
        if self.list_handler.get_unsaved() != "":
            return "Exceptions for disposable templates "
        return ""

    def reset(self):
        self.initialize()

    def save(self):
        self.policy_manager.save_rules(
            self.policy_file_name,
            self.list_handler.current_rules, self.current_token)

        _, self.current_token = self.policy_manager.get_rules_from_filename(
            self.policy_file_name, "")

        self.initial_rules = deepcopy(self.list_handler.current_rules)
